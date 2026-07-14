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
    get_block_children,
    update_page_properties,
)
from app.notion.dashboard_blocks import (
    APPLIED_COUNT_BLOCK_INDEX,
    DISCOVERED_COUNT_BLOCK_INDEX,
    build_dashboard_blocks,
)
from app.notion.guide_parser import render_guide_blocks
from app.notion.rich_text import bulleted_rich, heading3, link_text, text
from app.notion.schemas import (
    OPPORTUNITY_TITLE_PROP,
    ROADMAP_TITLE_PROP,
    TEAM_TITLE_PROP,
    number_value,
    opportunity_map_properties_schema,
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


def _ensure_workspace(
    session: Session, account_id: str, parent_page_id: str, headers: dict[str, str]
) -> WorkspaceRecord:
    existing = get_workspace(session, account_id)
    if existing is not None:
        return existing

    # 대시보드 페이지를 먼저 만들고, 데이터베이스 3개를 이 페이지를 parent로 생성한다 —
    # 그러면 Notion이 각 데이터베이스의 child_database 블록을 페이지 끝에 자동으로 붙여준다
    # (dashboard_blocks.py 상단 docstring 참고).
    dashboard_page = create_page(parent_page_id, "AX 대시보드", build_dashboard_blocks(), headers)
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


def _upsert_member(
    session: Session, account_id: str, member: TeamMemberTag, team_data_source_id: str, headers: dict[str, str]
) -> str:
    properties = {
        TEAM_TITLE_PROP: title_value(member.member_id),
        "강점": rich_text_value(", ".join(member.strengths)),
        "AI 활용 편안함": rich_text_value(member.ai_comfort_level),
        "업무부담": rich_text_value(member.workload_level),
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
    workspace = _ensure_workspace(session, account_id, parent_page_id, headers)

    for member in onboarding.member_tags:
        _upsert_member(session, account_id, member, workspace.team_data_source_id, headers)

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
