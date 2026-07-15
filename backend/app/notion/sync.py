"""
notion/sync.py

RoadmapResult(+ OnboardingData) -> 팀원/Opportunity Map/Roadmap 데이터베이스 upsert 오케스트레이션,
그리고 MaturityDiagnosis -> "AX 성숙도 진단" 데이터베이스 append(이력 쌓기) 오케스트레이션.
데이터베이스 4종·대시보드 페이지는 계정당 1회만 만들고(`tracking_repository`가 재사용 여부 판단),
Opportunity Map/Roadmap/팀원 행은 work_item_id/task_id/member_id 기준으로 있으면 갱신·없으면 생성한다.
"AX 성숙도 진단"은 재평가할 때마다 새 회차를 쌓는 이력 테이블이라 upsert 대상 키가 없다 — 발행할
때마다 새 행을 추가한다(QA_amendments 2절 "향후 주간 진단 추가 시 재평가 가능하도록").

2026-07-15: 지표 대시보드(QA_amendments 2절 20번, "AX 기회"·"카테고리별 Task 개수"·"진행도" 차트
3개를 한 화면에 모아 보여주는 것)는 자동 발행 대상에서 뺐다. 두 가지 방법을 실 계정으로 시도했다 —
① Notion의 "Dashboard" 뷰(여러 데이터소스의 위젯을 한 화면에 배치)는 **유료 플랜 전용**이라
무료 플랜에서는 위젯 생성이 막혀 있었다(사용자 확인). ② 대안으로 각 DB에 딸린 평범한 "chart" 뷰
3개(donut/bar×2)를 만드는 것까지는 성공했지만, 그러면 각 뷰가 원래 속한 데이터베이스(Opportunity
Map/Roadmap)의 탭으로 들어가 버려 사용자가 원한 "페이지 맨 위 별도 섹션·2열 배치"가 아니었다.
그 배치를 내려면 다른 데이터베이스를 원본으로 하는 "연결된 데이터베이스(linked database)"를
별도 위치에 만들어야 하는데, 공개 API는 이를 지원하지 않는다(makenotion/notion-sdk-js #547 —
"linked data sources"는 API 미지원으로 공식 확인됨). 그래서 억지로 비슷하게 만들지 않고
차트 자동 생성 자체를 뺐다 — 사용자가 Notion에서 `/linked`로 직접 만드는 걸 권장한다(최종 보고
참고). Layer를 select 속성으로 바꾼 것(schemas.py의 OPPORTUNITY_LAYER_PROP)은 그대로 남겨뒀다 —
수동으로 도넛 차트를 만들 때도 number보다 select가 그룹핑에 필요해서 여전히 유용하다.
"""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.contracts.goal import GoalDefinition
from app.contracts.maturity import MATURITY_AXES, MaturityDiagnosis
from app.contracts.onboarding import OnboardingData, TeamMemberTag
from app.contracts.research import ResearchContext
from app.contracts.roadmap import FitnessAssessment, Metric, RoadmapResult, Task
from app.notion.client import (
    create_database,
    create_database_row,
    create_page,
    get_block_children,
    get_data_source,
    get_page,
    list_views,
    update_callout_text,
    update_data_source_properties,
    update_page_properties,
    update_view_configuration,
    update_view_sorts,
)
from app.notion.dashboard_blocks import build_dashboard_blocks, goal_callout_text
from app.notion.guide_parser import render_guide_blocks
from app.notion.rich_text import bulleted_rich, heading3, link_text, text
from app.notion.schemas import (
    MATURITY_PRIORITY_PROP,
    MATURITY_SUMMARY_PROP,
    MATURITY_TITLE_PROP,
    OPPORTUNITY_FITNESS_PROP,
    OPPORTUNITY_LAYER_PROP,
    OPPORTUNITY_TASK_RELATION_PROP,
    OPPORTUNITY_TITLE_PROP,
    ROADMAP_MEMBER_RELATION_PROP,
    ROADMAP_OBJECTIVE_RELATION_PROP,
    ROADMAP_STARTED_PROP,
    ROADMAP_TITLE_PROP,
    ROADMAP_WEEK_PROP,
    ROADMAP_WORK_ITEM_RELATION_PROP,
    TEAM_ASSIGNED_TASK_RELATION_PROP,
    TEAM_PROGRESS_PROP,
    TEAM_TITLE_PROP,
    checkbox_value,
    layer_select_name,
    maturity_properties_schema,
    number_value,
    opportunity_map_properties_schema,
    opportunity_progress_rollup_property,
    relation_value,
    rich_text_value,
    roadmap_properties_schema,
    roadmap_relation_properties,
    select_value,
    team_properties_schema,
    title_value,
)
from app.notion.tracking_repository import (
    WorkspaceRecord,
    forget_workspace,
    get_member_page_id,
    get_task_page_id,
    get_work_item_page_id,
    get_workspace,
    save_maturity_database,
    save_member_page,
    save_task_page,
    save_work_item_page,
    save_workspace,
)

# Notion 기본 제공 커버 이미지(Notion 자체 CDN 호스팅 — 별도 이미지 호스팅 불필요, 실 URL 확인됨).
# James Webb 우주망원경 사진이라 AX/AI 전환이라는 주제와 어울리는 "tech" 톤을 준다(QA_amendments 2절).
_DASHBOARD_COVER_URL = "https://www.notion.so/images/page-cover/webb1.jpg"


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


def _rename_property(data_source_id: str, current_name: str, new_name: str, headers: dict[str, str]) -> None:
    schema = get_data_source(data_source_id, headers)
    prop_id = schema["properties"][current_name]["id"]
    update_data_source_properties(data_source_id, {prop_id: {"name": new_name}}, headers)


def _default_table_view_id(database_id: str, headers: dict[str, str]) -> str | None:
    """`create_database` 직후에 부르면 Notion이 자동으로 만든 기본 "Table" 뷰 하나만 있다 —
    이후 컬럼 순서·정렬을 조정할 대상 view_id를 여기서 얻는다. 못 찾으면 None(뷰 정렬은 건너뛴다 —
    치명적이지 않은 화면 정리용 기능이라 여기서 실패해도 발행 전체가 실패하면 안 된다)."""
    views = list_views(database_id, headers)
    return views[0]["id"] if views else None


def _set_table_column_order(
    data_source_id: str, view_id: str, property_names_in_order: list[str], headers: dict[str, str]
) -> None:
    """표 뷰의 컬럼(속성) 순서를 QA_amendments가 지정한 순서로 맞춘다."""
    schema = get_data_source(data_source_id, headers)
    ids_by_name = {name: prop["id"] for name, prop in schema["properties"].items()}
    properties = [
        {"property_id": ids_by_name[name], "visible": True}
        for name in property_names_in_order
        if name in ids_by_name
    ]
    update_view_configuration(view_id, {"type": "table", "properties": properties}, headers)


def _sort_table_by_select_ascending(view_id: str, property_name: str, headers: dict[str, str]) -> None:
    update_view_sorts(view_id, [{"property": property_name, "direction": "ascending"}], headers)


def _dashboard_page_still_usable(dashboard_page_id: str, headers: dict[str, str]) -> bool:
    """저장해 둔 대시보드 페이지가 지금도 실제로 쓸 수 있는지 확인한다 — 지워졌거나(404) 휴지통에
    들어갔으면(in_trash) 그 아래에 아무것도 만들 수 없다. 조회 자체가 실패해도(네트워크 문제 등)
    안전한 쪽으로 판단해 재사용을 포기하고 새로 만든다."""
    try:
        page = get_page(dashboard_page_id, headers)
    except Exception:
        return False
    return not page.get("in_trash", False)


def _ensure_workspace(
    session: Session, account_id: str, parent_page_id: str, headers: dict[str, str], goal_text: str = ""
) -> WorkspaceRecord:
    existing = get_workspace(session, account_id)
    if existing is not None:
        if _dashboard_page_still_usable(existing.dashboard_page_id, headers):
            return existing
        # 저장된 대시보드 페이지가 Notion에서 삭제되거나 휴지통에 들어가 더 이상 못 쓴다 — 테스트/
        # 정리 중 대시보드 페이지가 지워지는 사고가 실 운영에서 세 번이나 반복됐다(2026-07-15).
        # 예전엔 이걸 사람이 직접 DB에서 지워줘야 했는데, 이제 발행 자체가 스스로 감지하고
        # 새 워크스페이스를 만든다 — 옛 매핑이 남아있으면 새 데이터베이스에 옛 페이지 ID로 잘못
        # 업데이트를 시도하니 먼저 싹 지운다.
        forget_workspace(session, account_id)

    # 대시보드 페이지를 먼저 만들고, 데이터베이스들을 이 페이지를 parent로 생성한다 — 그러면
    # Notion이 각 데이터베이스의 child_database 블록을 페이지 끝에 "생성한 순서대로" 자동으로
    # 붙여준다(dashboard_blocks.py 상단 docstring 참고, 블록은 API로 재정렬 불가). QA_amendments
    # 2절이 요구하는 화면 순서(목표 콜아웃 - Roadmap - Opportunity Map - 팀원 - 성숙도 진단, "지표
    # 대시보드"는 별도 블록이 아니라 Roadmap/Opportunity Map DB에 딸린 차트 뷰 탭이라 순서에서 제외)를
    # 맞추려면 Roadmap을 가장 먼저 만들어야 하는데, Roadmap 스키마의 Objective/담당자
    # relation은 Opportunity Map·팀원의 data_source_id를 필요로 해서 원래는 나중에 만들어야 했다.
    # 그래서 Roadmap을 relation 없이 먼저 만들고(roadmap_properties_schema), 나머지 두 DB를 만든
    # 뒤 relation 두 개를 PATCH로 덧붙인다(roadmap_relation_properties) — Total Progress rollup을
    # 나중에 추가하는 것과 같은 패턴이라 이미 실 API로 검증된 방식의 연장이다.
    dashboard_page = create_page(
        parent_page_id,
        "AX 대시보드",
        build_dashboard_blocks(goal_text),
        headers,
        icon="🧭",
        cover_url=_DASHBOARD_COVER_URL,
    )
    dashboard_page_id = dashboard_page["id"]

    roadmap_db = create_database(dashboard_page_id, "Roadmap", roadmap_properties_schema(), headers)
    opportunity_db = create_database(
        dashboard_page_id, "Opportunity Map", opportunity_map_properties_schema(), headers
    )
    team_db = create_database(dashboard_page_id, "팀원", team_properties_schema(), headers)

    update_data_source_properties(
        roadmap_db["data_source_id"],
        roadmap_relation_properties(opportunity_db["data_source_id"], team_db["data_source_id"]),
        headers,
    )

    # Roadmap의 Objective/담당자를 dual_property로 만들면 Notion이 Opportunity Map/팀원 쪽에
    # 기본 이름("Related to Roadmap (...)")으로 역방향 속성을 자동으로 붙인다 — 사용자 제공
    # 템플릿과 같은 이름("Task"/"담당 업무")으로 바꾸고, Opportunity Map엔 그 relation을 통해
    # Roadmap.Progress를 평균 내는 "Total Progress" rollup도 추가한다. 역방향 lookup은
    # synced_property_name이 "현재" Roadmap 쪽 정방향 속성 이름을 그대로 따라오므로, 아직
    # "Objective"일 때(다음 블록에서 "업무"로 개명하기 전) 먼저 해야 한다.
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
    # 정방향 relation도 사용자 제공 템플릿 이름("업무")으로 개명 — QA_amendments 2절 "Roadmap 열
    # 순서 정렬: ... 업무(기존 Objective 명칭 변경)". 이후 값을 써넣을 땐(_upsert_task) 이 새
    # 이름을 property key로 써야 한다.
    _rename_property(
        roadmap_db["data_source_id"], ROADMAP_OBJECTIVE_RELATION_PROP, ROADMAP_WORK_ITEM_RELATION_PROP, headers
    )

    # 표 뷰 컬럼 순서·행 정렬(QA_amendments 2절 Roadmap/Opportunity Map 절) — 실패해도 발행 자체를
    # 막지 않는다(화면 정리용이라 콘텐츠 정합성보다 우선순위가 낮음).
    roadmap_table_view_id = _default_table_view_id(roadmap_db["database_id"], headers)
    if roadmap_table_view_id:
        _set_table_column_order(
            roadmap_db["data_source_id"],
            roadmap_table_view_id,
            [
                ROADMAP_WEEK_PROP,
                "category",
                ROADMAP_TITLE_PROP,
                ROADMAP_WORK_ITEM_RELATION_PROP,
                ROADMAP_STARTED_PROP,
                "Progress",
                ROADMAP_MEMBER_RELATION_PROP,
                "지표명",
                "단위",
                "기존값",
                "현재값",
                "목표값",
            ],
            headers,
        )
    opportunity_table_view_id = _default_table_view_id(opportunity_db["database_id"], headers)
    if opportunity_table_view_id:
        _set_table_column_order(
            opportunity_db["data_source_id"],
            opportunity_table_view_id,
            [
                OPPORTUNITY_TITLE_PROP,
                "빈도",
                OPPORTUNITY_FITNESS_PROP,
                "Layer",
                OPPORTUNITY_TASK_RELATION_PROP,
                "Total Progress",
                "pivot 사유",
            ],
            headers,
        )
        _sort_table_by_select_ascending(opportunity_table_view_id, OPPORTUNITY_FITNESS_PROP, headers)

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
        goal_callout_block_id=dashboard_children[0]["id"],
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
        "주요 업무": rich_text_value(member.assigned_work),
        "AI 활용 편안함": rich_text_value(member.ai_comfort_level),
        "업무부담": rich_text_value(member.workload_level),
        "비고": rich_text_value(member.notes),
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
        OPPORTUNITY_LAYER_PROP: select_value(layer_select_name(fa.layer)),
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
        ROADMAP_WEEK_PROP: number_value(task.week),
        "category": select_value(task.category.value),
        "지표명": rich_text_value(metric.metric_name if metric else ""),
        "단위": rich_text_value(metric.unit if metric else ""),
        "기존값": number_value(metric.baseline_value if metric else None),
        "현재값": number_value(metric.current_value if metric else None),
        "목표값": number_value(metric.target_value if metric else None),
        ROADMAP_WORK_ITEM_RELATION_PROP: relation_value([work_item_page_id] if work_item_page_id else []),
        ROADMAP_MEMBER_RELATION_PROP: relation_value(member_page_ids),
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


def _update_goal_callout(workspace: WorkspaceRecord, goal_text: str, headers: dict[str, str]) -> None:
    """재발행마다 목표가 바뀔 수 있어(같은 계정이 goal을 다시 설정하는 경우), 워크스페이스
    최초 생성 시 1회만 쓰고 마는 게 아니라 매 발행마다 콜아웃 텍스트를 최신 목표로 갱신한다.
    색(purple_background)은 최초 생성 시 이미 고정되어 있어 텍스트만 바꾸면 된다."""
    if not workspace.goal_callout_block_id:
        return
    update_callout_text(workspace.goal_callout_block_id, goal_callout_text(goal_text), headers)


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
    _update_goal_callout(workspace, goal.goal_text, headers)

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


def _ensure_maturity_database(
    session: Session, workspace: WorkspaceRecord, headers: dict[str, str]
) -> tuple[str, str]:
    """"AX 성숙도 진단" DB는 첫 진단 발행 시점에만 만든다(진단 없이 로드맵만 발행하는 흐름도
    있어서 워크스페이스 생성 시점엔 아직 없을 수 있음). QA_amendments 2절 배치 순서상 항상
    맨 마지막(팀원 DB 다음)에 와야 하는데, 다른 DB들이 이미 만들어진 뒤에 생성되므로 자연히
    페이지 맨 끝에 붙는다."""
    if workspace.maturity_database_id and workspace.maturity_data_source_id:
        return workspace.maturity_database_id, workspace.maturity_data_source_id

    maturity_db = create_database(
        workspace.dashboard_page_id, "AX 성숙도 진단", maturity_properties_schema(), headers
    )
    save_maturity_database(session, workspace.account_id, maturity_db["database_id"], maturity_db["data_source_id"])
    workspace.maturity_database_id = maturity_db["database_id"]
    workspace.maturity_data_source_id = maturity_db["data_source_id"]
    return maturity_db["database_id"], maturity_db["data_source_id"]


def sync_diagnosis(
    diagnosis: MaturityDiagnosis, workspace: WorkspaceRecord, session: Session, headers: dict[str, str]
) -> str:
    """진단 결과를 "AX 성숙도 진단" DB에 새 행으로 추가한다(upsert 아님 — 매 회차가 이력으로
    쌓여야 다음 주간 진단과 비교할 수 있다, QA_amendments 2절)."""
    _, maturity_data_source_id = _ensure_maturity_database(session, workspace, headers)

    scores_by_axis = {s.axis: s for s in diagnosis.axis_scores}
    properties = {
        MATURITY_TITLE_PROP: title_value(datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")),
        MATURITY_SUMMARY_PROP: rich_text_value(diagnosis.summary),
        MATURITY_PRIORITY_PROP: rich_text_value(" → ".join(a.value for a in diagnosis.priority_axes)),
    }
    for axis in MATURITY_AXES:
        score = scores_by_axis.get(axis)
        properties[axis.value] = number_value(score.score if score else None)

    page = create_database_row(maturity_data_source_id, properties, headers)
    return page["id"]
