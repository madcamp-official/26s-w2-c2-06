"""
notion/sync.py

RoadmapResult(+ OnboardingData) -> 팀원/Opportunity Map/Roadmap 데이터베이스 upsert 오케스트레이션.
데이터베이스 3종·대시보드 페이지는 계정당 1회만 만들고(`tracking_repository`가 재사용 여부 판단),
행은 work_item_id/task_id/member_id 기준으로 있으면 갱신·없으면 생성한다.

**주의**: 실제 Notion 워크스페이스로 라이브 검증되지 않았다 — 계정 연결 후 스모크 테스트 필요
(SPRINT1_FEATURE4_ROADMAP_GENERATOR.md 9절).
"""

from sqlalchemy.orm import Session

from app.contracts.goal import GoalDefinition
from app.contracts.onboarding import OnboardingData, TeamMemberTag
from app.contracts.research import ResearchContext
from app.contracts.roadmap import FitnessAssessment, Metric, RoadmapResult, Task
from app.notion.client import (
    create_database,
    create_database_row,
    create_page,
    create_view,
    get_block_children,
    get_data_source,
    update_data_source_properties,
    update_page_properties,
    update_view_configuration,
)
from app.notion.dashboard_blocks import (
    APPLIED_COUNT_BLOCK_INDEX,
    DISCOVERED_COUNT_BLOCK_INDEX,
    build_dashboard_blocks,
)
from app.notion.guide_parser import render_guide_blocks
from app.notion.rich_text import bulleted_rich, heading3, link_text, text
from app.notion.schemas import (
    OPPORTUNITY_FITNESS_PROP,
    OPPORTUNITY_TASK_RELATION_PROP,
    OPPORTUNITY_TITLE_PROP,
    ROADMAP_MEMBER_RELATION_PROP,
    ROADMAP_OBJECTIVE_RELATION_PROP,
    ROADMAP_STARTED_PROP,
    ROADMAP_TITLE_PROP,
    TEAM_ASSIGNED_TASK_RELATION_PROP,
    TEAM_PROGRESS_PROP,
    TEAM_TITLE_PROP,
    checkbox_value,
    number_value,
    opportunity_map_properties_schema,
    opportunity_progress_rollup_property,
    relation_value,
    rich_text_value,
    roadmap_properties_schema,
    select_value,
    team_properties_schema,
    title_value,
)
from app.notion.tracking_repository import (
    WorkspaceRecord,
    get_member_page_id,
    get_task_page_id,
    get_work_item_page_id,
    get_workspace,
    save_member_page,
    save_task_page,
    save_work_item_page,
    save_workspace,
)


_DASHBOARD_COVER_URL = "https://placehold.co/1500x400/FCD34D/FCD34D.png"


def _reverse_relation_property_id(schema: dict, synced_property_name: str) -> str | None:
    for prop in schema.get("properties", {}).values():
        if prop.get("type") != "relation":
            continue
        dual = prop["relation"].get("dual_property")
        if dual and dual.get("synced_property_name") == synced_property_name:
            return prop["id"]
    return None


def _rename_reverse_relation(
    data_source_id: str, synced_property_name: str, new_name: str, headers: dict[str, str]
) -> None:
    """dual relation 생성 시 Notion이 자동으로 붙인 역방향 속성 이름("Related to Roadmap (...)")을
    찾아 우리가 원하는 이름으로 바꾼다. 생성 시점엔 이 이름을 지정할 방법이 없어(실 API 호출로 확인)
    생성 후 스키마를 다시 읽어 synced_property_name으로 대상을 찾는다."""
    schema = get_data_source(data_source_id, headers)
    prop_id = _reverse_relation_property_id(schema, synced_property_name)
    if prop_id is None:
        raise ValueError(f"역방향 relation 속성을 찾지 못했습니다: {synced_property_name}")
    update_data_source_properties(data_source_id, {prop_id: {"name": new_name}}, headers)


def _add_fitness_distribution_chart(
    opportunity_database_id: str, opportunity_data_source_id: str, headers: dict[str, str]
) -> None:
    """Opportunity Map에 "적합성 분포" 도넛 차트 뷰를 추가한다.

    9절엔 "공개 API는 차트 뷰를 못 만든다"고 적혀 있었는데, 실제로 `/v1/views`로 라이브 호출해보니
    되는 걸 확인했다(2026-07-15) — 그 기록은 더 이상 사실이 아니라 이 함수가 새 근거다. donut
    차트는 생성 시점엔 configuration이 비어 있어, x_axis(select 속성의 property_id + sort)까지
    채우는 PATCH가 한 번 더 필요하다(실 API 호출로 확인한 필수 필드).
    """
    schema = get_data_source(opportunity_data_source_id, headers)
    fitness_property_id = schema["properties"][OPPORTUNITY_FITNESS_PROP]["id"]

    view = create_view(opportunity_database_id, opportunity_data_source_id, "적합성 분포", "chart", headers)
    update_view_configuration(
        view["id"],
        {
            "type": "chart",
            "chart_type": "donut",
            "x_axis": {"type": "select", "property_id": fitness_property_id, "sort": {"type": "descending"}},
        },
        headers,
    )


def _add_team_progress_chart(
    team_database_id: str, team_data_source_id: str, headers: dict[str, str]
) -> None:
    """팀원 DB에 "Task별 진행률" 세로 막대(column) 차트 뷰를 추가한다 — x축은 팀원 이름(title,
    정확히 일치하는 값별로 그룹핑 = "exact"), y축은 그 팀원이 맡은 task들의 평균 진행률이다.
    이 값은 rollup이 아니라 `_upsert_member`가 RoadmapResult에서 직접 계산해 써넣은 순수
    number다 — rollup/formula를 차트 축으로 쓰면 렌더링이 깨지는 걸 실측으로 확인했기 때문
    (schemas.py 상단 docstring 참고). chart_type은 "column"(세로)/"bar"(가로)가 따로 있다는
    것과, title처럼 select가 아닌 속성으로 그룹핑할 때는 x_axis.group_by가 별도로 필요하다는
    것도 실 API 호출로 확인해서 반영했다."""
    schema = get_data_source(team_data_source_id, headers)
    title_property_id = schema["properties"][TEAM_TITLE_PROP]["id"]
    progress_property_id = schema["properties"][TEAM_PROGRESS_PROP]["id"]

    view = create_view(team_database_id, team_data_source_id, "Task별 진행률", "chart", headers)
    update_view_configuration(
        view["id"],
        {
            "type": "chart",
            "chart_type": "column",
            "x_axis": {
                "type": "title",
                "property_id": title_property_id,
                "group_by": "exact",
                "sort": {"type": "ascending"},
            },
            "y_axis": {"property_id": progress_property_id, "aggregator": "average"},
        },
        headers,
    )


def _add_ax_adoption_chart(
    roadmap_database_id: str, roadmap_data_source_id: str, headers: dict[str, str]
) -> None:
    """Roadmap DB에 "AX 적용 현황" 뷰를 추가한다 — 그룹별 분포가 아니라 "착수 여부"가 체크된
    task 수 하나만 큰 숫자로 보여주는 chart_type="number"를 쓴다. number 타입은 x_axis/y_axis가
    아니라 "value"(aggregator="checked" — Notion 표 하단의 체크박스 "Checked Count" 요약과
    같음) 하나만 받는다는 걸 실 API 호출로 확인해서 반영했다. "착수 여부"는 formula가 아니라
    `_upsert_task`가 기존값/현재값을 비교해 직접 써넣는 순수 checkbox다(rollup/formula를 차트
    집계 대상으로 쓰면 렌더링이 깨지는 걸 실측으로 확인했기 때문)."""
    schema = get_data_source(roadmap_data_source_id, headers)
    started_property_id = schema["properties"][ROADMAP_STARTED_PROP]["id"]

    view = create_view(roadmap_database_id, roadmap_data_source_id, "AX 적용 현황", "chart", headers)
    update_view_configuration(
        view["id"],
        {
            "type": "chart",
            "chart_type": "number",
            "value": {"property_id": started_property_id, "aggregator": "checked"},
        },
        headers,
    )


def _ensure_workspace(
    session: Session, account_id: str, parent_page_id: str, headers: dict[str, str], goal_text: str = ""
) -> WorkspaceRecord:
    existing = get_workspace(session, account_id)
    if existing is not None:
        return existing

    # 대시보드 페이지를 먼저 만들고, 데이터베이스 3개를 이 페이지를 parent로 생성한다 —
    # 그러면 Notion이 각 데이터베이스의 child_database 블록을 페이지 끝에 자동으로 붙여준다
    # (dashboard_blocks.py 상단 docstring 참고). 아이콘은 이 앱에서 이미 쓰는 나침반(🧭, 진단
    # 콜아웃과 동일)으로, 배너는 사용자 제공 템플릿과 같은 톤의 노란색 배경으로 통일한다
    # (placehold.co — 실제 이미지 호스팅 없이 고정 색상 이미지를 만들어주는 공개 서비스).
    dashboard_page = create_page(
        parent_page_id,
        "AX 대시보드",
        build_dashboard_blocks(goal_text),
        headers,
        icon="🧭",
        cover_url=_DASHBOARD_COVER_URL,
    )
    dashboard_page_id = dashboard_page["id"]

    team_db = create_database(dashboard_page_id, "팀원", team_properties_schema(), headers)
    opportunity_db = create_database(
        dashboard_page_id, "Opportunity Map", opportunity_map_properties_schema(), headers
    )
    roadmap_db = create_database(
        dashboard_page_id,
        "Roadmap",
        roadmap_properties_schema(opportunity_db["data_source_id"], team_db["data_source_id"]),
        headers,
    )

    # Roadmap의 Objective/담당자를 dual_property로 만들면 Notion이 Opportunity Map/팀원 쪽에
    # 기본 이름("Related to Roadmap (...)")으로 역방향 속성을 자동으로 붙인다 — 사용자 제공
    # 템플릿과 같은 이름("Task"/"담당 업무")으로 바꾸고, Opportunity Map엔 그 relation을 통해
    # Roadmap.Progress를 평균 내는 "Total Progress" rollup도 추가한다.
    _rename_reverse_relation(
        opportunity_db["data_source_id"], ROADMAP_OBJECTIVE_RELATION_PROP, OPPORTUNITY_TASK_RELATION_PROP, headers
    )
    _rename_reverse_relation(
        team_db["data_source_id"], ROADMAP_MEMBER_RELATION_PROP, TEAM_ASSIGNED_TASK_RELATION_PROP, headers
    )
    update_data_source_properties(
        opportunity_db["data_source_id"],
        opportunity_progress_rollup_property(OPPORTUNITY_TASK_RELATION_PROP),
        headers,
    )
    _add_fitness_distribution_chart(opportunity_db["database_id"], opportunity_db["data_source_id"], headers)
    _add_team_progress_chart(team_db["database_id"], team_db["data_source_id"], headers)
    _add_ax_adoption_chart(roadmap_db["database_id"], roadmap_db["data_source_id"], headers)

    dashboard_children = get_block_children(dashboard_page_id, headers)

    record = WorkspaceRecord(
        account_id=account_id,
        team_database_id=team_db["database_id"],
        team_data_source_id=team_db["data_source_id"],
        opportunity_database_id=opportunity_db["database_id"],
        opportunity_data_source_id=opportunity_db["data_source_id"],
        roadmap_database_id=roadmap_db["database_id"],
        roadmap_data_source_id=roadmap_db["data_source_id"],
        dashboard_page_id=dashboard_page_id,
        dashboard_url=dashboard_page["url"],
        discovered_count_block_id=dashboard_children[DISCOVERED_COUNT_BLOCK_INDEX]["id"],
        applied_count_block_id=dashboard_children[APPLIED_COUNT_BLOCK_INDEX]["id"],
    )
    save_workspace(session, record)
    return record


def _progress_fraction(metric: Metric) -> float:
    """Notion "Progress" formula와 동일한 계산을 파이썬으로 그대로 옮긴 것 — 팀원별 평균 진행률
    (rollup이 아닌 순수 number로 차트에 써야 함, schemas.py 상단 docstring 참고) 계산에 쓴다."""
    if metric.target_value == metric.baseline_value:
        return 1.0
    fraction = (metric.current_value - metric.baseline_value) / (metric.target_value - metric.baseline_value)
    return max(0.0, min(1.0, fraction))


def _member_avg_progress(roadmap: RoadmapResult) -> dict[str, float]:
    """담당자별로 맡은 task들의 진행률 평균을 계산한다. task 하나에 담당자가 여럿이면 그 task의
    진행률이 각 담당자 평균에 모두 반영된다."""
    metrics_by_task = {m.task_id: m for m in roadmap.metrics}
    members_by_task = {s.task_id: s.assigned_member_ids for s in roadmap.role_reassignment_suggestions}

    progress_by_member: dict[str, list[float]] = {}
    for task in roadmap.tasks:
        metric = metrics_by_task.get(task.task_id)
        if metric is None:
            continue
        fraction = _progress_fraction(metric)
        for member_id in members_by_task.get(task.task_id, []):
            progress_by_member.setdefault(member_id, []).append(fraction)

    return {
        member_id: sum(fractions) / len(fractions) for member_id, fractions in progress_by_member.items()
    }


def _upsert_member(
    session: Session,
    account_id: str,
    member: TeamMemberTag,
    team_data_source_id: str,
    headers: dict[str, str],
    avg_progress: float | None,
) -> str:
    properties = {
        TEAM_TITLE_PROP: title_value(member.member_id),
        "강점": rich_text_value(", ".join(member.strengths)),
        "AI 활용 편안함": rich_text_value(member.ai_comfort_level),
        "업무부담": rich_text_value(member.workload_level),
        TEAM_PROGRESS_PROP: number_value(avg_progress),
    }

    page_id = get_member_page_id(session, account_id, member.member_id)
    if page_id:
        update_page_properties(page_id, properties, headers)
        return page_id

    page = create_database_row(team_data_source_id, properties, headers)
    save_member_page(session, account_id, member.member_id, page["id"])
    return page["id"]


def _upsert_work_item(
    session: Session,
    account_id: str,
    goal_id: str,
    fa: FitnessAssessment,
    opportunity_data_source_id: str,
    headers: dict[str, str],
) -> str:
    properties = {
        OPPORTUNITY_TITLE_PROP: title_value(fa.task_candidate),
        "빈도": select_value(fa.frequency_bucket.value),
        "적합성": select_value(fa.fitness.value),
        "Layer": number_value(fa.layer),
        "pivot 사유": rich_text_value(fa.reason if fa.fitness.value == "부적합" else ""),
    }

    page_id = get_work_item_page_id(session, account_id, goal_id, fa.work_item_id)
    if page_id:
        update_page_properties(page_id, properties, headers)
        return page_id

    page = create_database_row(opportunity_data_source_id, properties, headers)
    save_work_item_page(session, account_id, goal_id, fa.work_item_id, page["id"])
    return page["id"]


def _source_ref_blocks(task: Task, research: ResearchContext | None) -> list[dict]:
    """근거를 실제로 클릭해서 확인할 수 있게 source_url을 링크로 건다.
    ResearchContext 자체(search_queries 등)는 노출하지 않는다 — 인용의 출처는
    source_url/metric_snippet뿐이라는 계약 §4 규약을 따른다."""
    if not task.source_refs:
        return []

    findings_by_id = {f.finding_id: f for f in research.findings} if research else {}
    entries = []
    for ref in task.source_refs:
        finding = findings_by_id.get(ref)
        if finding is None:
            entries.append(bulleted_rich([text(f"({ref})")]))
            continue
        spans = [link_text(finding.source_title, finding.source_url), text(f" — {finding.summary}")]
        if finding.metric_snippet:
            spans.append(text(f" ({finding.metric_snippet})"))
        entries.append(bulleted_rich(spans))
    return [heading3("참고한 리서치 자료"), *entries]


def _upsert_task(
    session: Session,
    account_id: str,
    goal_id: str,
    task: Task,
    metric: Metric | None,
    work_item_page_id: str | None,
    member_page_ids: list[str],
    roadmap_data_source_id: str,
    headers: dict[str, str],
    research: ResearchContext | None = None,
) -> str:
    properties = {
        ROADMAP_TITLE_PROP: title_value(task.title),
        "category": select_value(task.category.value),
        "지표명": rich_text_value(metric.metric_name if metric else ""),
        "단위": rich_text_value(metric.unit if metric else ""),
        "기존값": number_value(metric.baseline_value if metric else None),
        "현재값": number_value(metric.current_value if metric else None),
        "목표값": number_value(metric.target_value if metric else None),
        "Objective": relation_value([work_item_page_id] if work_item_page_id else []),
        "담당자": relation_value(member_page_ids),
        ROADMAP_STARTED_PROP: checkbox_value(
            metric is not None and metric.current_value != metric.baseline_value
        ),
    }
    blocks = render_guide_blocks(task.detailed_guide) + _source_ref_blocks(task, research)

    page_id = get_task_page_id(session, account_id, goal_id, task.task_id)
    if page_id:
        update_page_properties(page_id, properties, headers)
        return page_id

    page = create_database_row(roadmap_data_source_id, properties, headers, blocks=blocks)
    save_task_page(session, account_id, goal_id, task.task_id, page["id"])
    return page["id"]


def sync_roadmap(
    goal: GoalDefinition,
    roadmap: RoadmapResult,
    onboarding: OnboardingData,
    account_id: str,
    parent_page_id: str,
    session: Session,
    headers: dict[str, str],
    research: ResearchContext | None = None,
) -> WorkspaceRecord:
    """팀원 -> Opportunity Map -> Roadmap 순으로 upsert한다(뒤 단계가 앞 단계의 relation을 참조)."""
    workspace = _ensure_workspace(session, account_id, parent_page_id, headers, goal.goal_text)

    member_progress = _member_avg_progress(roadmap)
    for member in onboarding.member_tags:
        _upsert_member(
            session,
            account_id,
            member,
            workspace.team_data_source_id,
            headers,
            member_progress.get(member.member_id),
        )

    for fa in roadmap.fitness_assessment:
        _upsert_work_item(
            session, account_id, goal.goal_id, fa, workspace.opportunity_data_source_id, headers
        )

    metrics_by_task = {m.task_id: m for m in roadmap.metrics}
    members_by_task = {
        s.task_id: s.assigned_member_ids for s in roadmap.role_reassignment_suggestions
    }

    for task in roadmap.tasks:
        work_item_page_id = get_work_item_page_id(
            session, account_id, goal.goal_id, task.work_item_id
        )
        member_ids = members_by_task.get(task.task_id, [])
        member_page_ids = [
            page_id
            for member_id in member_ids
            if (page_id := get_member_page_id(session, account_id, member_id)) is not None
        ]
        _upsert_task(
            session,
            account_id,
            goal.goal_id,
            task,
            metrics_by_task.get(task.task_id),
            work_item_page_id,
            member_page_ids,
            workspace.roadmap_data_source_id,
            headers,
            research,
        )

    return workspace
