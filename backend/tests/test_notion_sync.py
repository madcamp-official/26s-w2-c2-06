import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.notion.sync as sync_module
from app.contracts.goal import GoalDefinition, OrgConstraints
from app.contracts.onboarding import OnboardingData, TeamMemberTag
from app.contracts.research import ResearchStatus
from app.contracts.roadmap import (
    FitnessAssessment,
    FitnessVerdict,
    FrequencyBucket,
    Metric,
    RoadmapResult,
    RoleReassignmentSuggestion,
    Task,
    TaskCategory,
)
from app.core.db import Base
from app.notion.tracking_repository import get_task_page_id, get_work_item_page_id


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    yield db
    db.close()


def _goal() -> GoalDefinition:
    return GoalDefinition(
        goal_id="goal_001", goal_text="목표", org_constraints=OrgConstraints(security_level="high")
    )


def _onboarding() -> OnboardingData:
    return OnboardingData(
        team_size=1,
        member_tags=[TeamMemberTag(member_id="M1", ai_comfort_level="중간", workload_level="중간")],
    )


def _roadmap() -> RoadmapResult:
    return RoadmapResult(
        goal_id="goal_001",
        research_status=ResearchStatus.OK,
        fitness_assessment=[
            FitnessAssessment(
                work_item_id="wi_001",
                task_candidate="월간 보고서 작성",
                matrix_position="자주+비정형",
                fitness=FitnessVerdict.FIT,
                layer=2,
                frequency_bucket=FrequencyBucket.MONTHLY,
                verdict="적합",
                reason="생성형 AI 최적 영역",
            )
        ],
        tasks=[
            Task(
                task_id="task_001",
                work_item_id="wi_001",
                title="보고서 초안 자동 생성",
                layer=2,
                week=1,
                category=TaskCategory.AUTOMATION,
                difficulty="중",
                est_time="30분",
                expected_effect="시간 절감",
                failure_risk="초안 품질 편차",
                detailed_guide="1. Copilot을 연다\n2. 프롬프트를 입력한다",
            )
        ],
        role_reassignment_suggestions=[
            RoleReassignmentSuggestion(task_id="task_001", assigned_member_ids=["M1"], reason="강점 일치")
        ],
        metrics=[
            Metric(
                task_id="task_001", metric_name="소요시간", unit="분", baseline_value=180, target_value=30
            )
        ],
    )


class _FakeCounter:
    def __init__(self):
        self.n = 0

    def next(self, prefix: str) -> str:
        self.n += 1
        return f"{prefix}-{self.n}"


def _patch_notion_api(monkeypatch):
    counter = _FakeCounter()
    calls = {
        "create_database": [],
        "create_database_row": [],
        "update_page_properties": [],
        "update_data_source_properties": [],
    }

    def fake_create_page(parent_page_id, title, blocks, headers, icon=None, cover_url=None):
        calls.setdefault("create_page_icon", []).append(icon)
        calls.setdefault("create_page_blocks", []).append(blocks)
        calls.setdefault("create_page_cover_url", []).append(cover_url)
        return {"id": counter.next("dash-page"), "url": "https://notion.so/dash-page"}

    def fake_create_database(parent_page_id, title, properties, headers):
        calls["create_database"].append(title)
        db_id = counter.next(f"db-{title}")
        return {"database_id": db_id, "data_source_id": f"{db_id}-ds"}

    def fake_get_block_children(block_id, headers):
        return [{"id": "discovered-block"}, {"id": "applied-block"}]

    def fake_create_database_row(data_source_id, properties, headers, blocks=None):
        calls["create_database_row"].append(data_source_id)
        calls.setdefault("blocks", []).append(blocks)
        return {"id": counter.next("row"), "url": "https://notion.so/row"}

    def fake_update_page_properties(page_id, properties, headers):
        calls["update_page_properties"].append(page_id)

    def fake_get_data_source(data_source_id, headers):
        # dual relation의 역방향 속성을 찾는 코드가 실제 응답 모양을 그대로 흉내낸 스키마에서
        # synced_property_name을 찾을 수 있도록, 어느 DB를 조회했는지에 따라 다른 값을 되돌려준다.
        if "Opportunity" in data_source_id:
            synced_name = "Objective"
        elif "팀원" in data_source_id:
            synced_name = "담당자"
        else:
            synced_name = "?"
        properties = {
            "Related to Roadmap": {
                "id": "auto-prop-id",
                "type": "relation",
                "relation": {"dual_property": {"synced_property_name": synced_name}},
            }
        }
        if "Opportunity" in data_source_id:
            properties["적합성"] = {"id": "fitness-prop-id", "type": "select"}
        if "팀원" in data_source_id:
            properties["팀원"] = {"id": "team-title-prop-id", "type": "title"}
            properties["Task 진행률"] = {"id": "team-progress-prop-id", "type": "rollup"}
        if "Roadmap" in data_source_id:
            properties["착수 여부"] = {"id": "started-prop-id", "type": "formula"}
        return {"properties": properties}

    def fake_update_data_source_properties(data_source_id, properties, headers):
        calls["update_data_source_properties"].append((data_source_id, properties))

    def fake_create_view(database_id, data_source_id, name, view_type, headers):
        calls.setdefault("create_view", []).append((database_id, data_source_id, name, view_type))
        return {"id": counter.next("view")}

    def fake_update_view_configuration(view_id, configuration, headers):
        calls.setdefault("update_view_configuration", []).append((view_id, configuration))

    monkeypatch.setattr(sync_module, "create_page", fake_create_page)
    monkeypatch.setattr(sync_module, "create_database", fake_create_database)
    monkeypatch.setattr(sync_module, "get_block_children", fake_get_block_children)
    monkeypatch.setattr(sync_module, "create_database_row", fake_create_database_row)
    monkeypatch.setattr(sync_module, "update_page_properties", fake_update_page_properties)
    monkeypatch.setattr(sync_module, "get_data_source", fake_get_data_source)
    monkeypatch.setattr(sync_module, "update_data_source_properties", fake_update_data_source_properties)
    monkeypatch.setattr(sync_module, "create_view", fake_create_view)
    monkeypatch.setattr(sync_module, "update_view_configuration", fake_update_view_configuration)

    return calls


def test_progress_fraction_clamps_and_handles_equal_baseline_target():
    from app.contracts.roadmap import Metric

    normal = Metric(task_id="t1", metric_name="m", unit="분", baseline_value=180, current_value=90, target_value=30)
    assert sync_module._progress_fraction(normal) == 0.6

    over_target = Metric(task_id="t1", metric_name="m", unit="분", baseline_value=180, current_value=0, target_value=30)
    assert sync_module._progress_fraction(over_target) == 1.0

    no_progress_yet = Metric(task_id="t1", metric_name="m", unit="분", baseline_value=180, current_value=180, target_value=30)
    assert sync_module._progress_fraction(no_progress_yet) == 0.0

    same_baseline_and_target = Metric(
        task_id="t1", metric_name="m", unit="건", baseline_value=5, current_value=5, target_value=5
    )
    assert sync_module._progress_fraction(same_baseline_and_target) == 1.0


def test_member_avg_progress_averages_across_assigned_tasks():
    from app.contracts.roadmap import Metric, RoleReassignmentSuggestion

    roadmap = _roadmap()
    roadmap.metrics = [
        Metric(task_id="task_001", metric_name="m", unit="분", baseline_value=100, current_value=50, target_value=0),
    ]
    roadmap.role_reassignment_suggestions = [
        RoleReassignmentSuggestion(task_id="task_001", assigned_member_ids=["M1", "M2"], reason="x"),
    ]

    result = sync_module._member_avg_progress(roadmap)

    assert result == {"M1": 0.5, "M2": 0.5}


def test_sync_roadmap_creates_workspace_and_rows_once(session, monkeypatch):
    calls = _patch_notion_api(monkeypatch)

    workspace = sync_module.sync_roadmap(
        _goal(), _roadmap(), _onboarding(), "acc-1", "parent-page", session, {}
    )

    assert sorted(calls["create_database"]) == ["Opportunity Map", "Roadmap", "팀원"]
    assert len(calls["create_database_row"]) == 3  # 팀원 1 + Opportunity Map 1 + Roadmap 1
    assert calls["update_page_properties"] == []

    assert get_work_item_page_id(session, "acc-1", "goal_001", "wi_001") is not None
    task_page_id = get_task_page_id(session, "acc-1", "goal_001", "task_001")
    assert task_page_id is not None
    assert workspace.roadmap_database_id.startswith("db-Roadmap")


def test_sync_roadmap_renames_reverse_relations_and_adds_progress_rollup(session, monkeypatch):
    calls = _patch_notion_api(monkeypatch)

    sync_module.sync_roadmap(_goal(), _roadmap(), _onboarding(), "acc-1", "parent-page", session, {})

    # Opportunity Map 쪽 역방향 relation("Objective"의 dual) -> "Task"로 개명
    opportunity_renames = [
        (ds_id, props)
        for ds_id, props in calls["update_data_source_properties"]
        if "Opportunity" in ds_id and any(v.get("name") == "Task" for v in props.values())
    ]
    assert len(opportunity_renames) == 1

    # 팀원 쪽 역방향 relation("담당자"의 dual) -> "담당 업무"로 개명
    team_renames = [
        (ds_id, props)
        for ds_id, props in calls["update_data_source_properties"]
        if "팀원" in ds_id and any(v.get("name") == "담당 업무" for v in props.values())
    ]
    assert len(team_renames) == 1

    # Opportunity Map에 Total Progress rollup 추가
    rollup_calls = [
        (ds_id, props)
        for ds_id, props in calls["update_data_source_properties"]
        if "Total Progress" in props
    ]
    assert len(rollup_calls) == 1
    assert rollup_calls[0][1]["Total Progress"]["rollup"]["relation_property_name"] == "Task"
    assert rollup_calls[0][1]["Total Progress"]["rollup"]["rollup_property_name"] == "Progress"


def test_sync_roadmap_sets_dashboard_icon_and_goal_intro_paragraph(session, monkeypatch):
    calls = _patch_notion_api(monkeypatch)

    sync_module.sync_roadmap(_goal(), _roadmap(), _onboarding(), "acc-1", "parent-page", session, {})

    assert calls["create_page_icon"] == ["🧭"]
    dashboard_blocks = calls["create_page_blocks"][0]
    paragraphs = [
        "".join(rt["plain_text"] if "plain_text" in rt else rt["text"]["content"] for rt in b["paragraph"]["rich_text"])
        for b in dashboard_blocks
        if b["type"] == "paragraph"
    ]
    assert any("목표" in p for p in paragraphs)


def test_sync_roadmap_adds_fitness_distribution_chart_to_opportunity_map(session, monkeypatch):
    calls = _patch_notion_api(monkeypatch)

    sync_module.sync_roadmap(_goal(), _roadmap(), _onboarding(), "acc-1", "parent-page", session, {})

    assert len(calls["create_view"]) == 3  # Opportunity Map·팀원·Roadmap 각 1개씩

    fitness_view = next(v for v in calls["create_view"] if v[2] == "적합성 분포")
    database_id, data_source_id, name, view_type = fitness_view
    assert "Opportunity" in database_id
    assert view_type == "chart"

    fitness_config = next(
        config for (view_id, config) in calls["update_view_configuration"]
        if config["x_axis"]["property_id"] == "fitness-prop-id"
    )
    assert fitness_config["chart_type"] == "donut"


def test_sync_roadmap_adds_team_progress_chart(session, monkeypatch):
    calls = _patch_notion_api(monkeypatch)

    sync_module.sync_roadmap(_goal(), _roadmap(), _onboarding(), "acc-1", "parent-page", session, {})

    team_view = next(v for v in calls["create_view"] if v[2] == "Task별 진행률")
    assert "팀원" in team_view[0]
    assert team_view[3] == "chart"

    team_config = next(
        config for (_, config) in calls["update_view_configuration"]
        if config["x_axis"].get("property_id") == "team-title-prop-id"
    )
    assert team_config["chart_type"] == "column"
    assert team_config["x_axis"]["group_by"] == "exact"
    assert team_config["y_axis"]["property_id"] == "team-progress-prop-id"
    assert team_config["y_axis"]["aggregator"] == "average"


def test_sync_roadmap_adds_ax_adoption_chart_to_roadmap(session, monkeypatch):
    calls = _patch_notion_api(monkeypatch)

    sync_module.sync_roadmap(_goal(), _roadmap(), _onboarding(), "acc-1", "parent-page", session, {})

    roadmap_view = next(v for v in calls["create_view"] if v[2] == "AX 적용 현황")
    assert "Roadmap" in roadmap_view[0]
    assert roadmap_view[3] == "chart"

    roadmap_config = next(
        config for (_, config) in calls["update_view_configuration"]
        if config.get("value", {}).get("property_id") == "started-prop-id"
    )
    assert roadmap_config["chart_type"] == "number"
    assert roadmap_config["value"]["aggregator"] == "checked"


def test_sync_roadmap_sets_yellow_dashboard_cover(session, monkeypatch):
    calls = _patch_notion_api(monkeypatch)

    sync_module.sync_roadmap(_goal(), _roadmap(), _onboarding(), "acc-1", "parent-page", session, {})

    assert calls["create_page_cover_url"] == [sync_module._DASHBOARD_COVER_URL]


def test_sync_roadmap_reuses_workspace_and_upserts_rows_on_second_call(session, monkeypatch):
    calls = _patch_notion_api(monkeypatch)

    sync_module.sync_roadmap(_goal(), _roadmap(), _onboarding(), "acc-1", "parent-page", session, {})
    sync_module.sync_roadmap(_goal(), _roadmap(), _onboarding(), "acc-1", "parent-page", session, {})

    # 워크스페이스(데이터베이스 3개)는 한 번만 만든다
    assert len(calls["create_database"]) == 3
    # 두 번째 호출은 같은 work_item_id/task_id/member_id라 새로 만들지 않고 갱신한다
    assert len(calls["create_database_row"]) == 3
    assert len(calls["update_page_properties"]) == 3


def test_sync_roadmap_renders_source_citation_links_in_task_page_when_research_given(session, monkeypatch):
    from app.contracts.research import Finding, ResearchContext

    calls = _patch_notion_api(monkeypatch)

    roadmap = _roadmap()
    roadmap.tasks[0].source_refs = ["F1"]
    research = ResearchContext(
        goal_id="goal_001",
        retrieved_at="2026-07-14T00:00:00Z",
        status=ResearchStatus.OK,
        findings=[
            Finding(
                finding_id="F1",
                source_title="사내 리포트",
                source_url="https://example.com/report",
                source_type="research",
                summary="요약문",
                relevant_method="사례 참고",
            )
        ],
    )

    sync_module.sync_roadmap(_goal(), roadmap, _onboarding(), "acc-1", "parent-page", session, {}, research)

    # create_database_row 호출 순서: 팀원 -> Opportunity Map -> Roadmap(task) 순이라 마지막이 task 블록
    task_blocks = calls["blocks"][-1]
    rich_text_spans = [
        span
        for block in task_blocks
        if block["type"] == "bulleted_list_item"
        for span in block["bulleted_list_item"]["rich_text"]
    ]
    assert any(span["text"].get("link", {}).get("url") == "https://example.com/report" for span in rich_text_spans)
