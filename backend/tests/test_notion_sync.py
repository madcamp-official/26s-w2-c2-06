import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.notion.sync as sync_module
from app.contracts.goal import GoalDefinition, OrgConstraints
from app.contracts.maturity import MATURITY_AXES, AxisScore, MaturityDiagnosis
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
from app.notion.tracking_repository import get_task_page_id, get_work_item_page_id, get_workspace


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    yield db
    db.close()


def _goal(text: str = "목표") -> GoalDefinition:
    return GoalDefinition(
        goal_id="goal_001", goal_text=text, org_constraints=OrgConstraints(security_level="high")
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


def _schema_for(data_source_id: str) -> dict:
    """실 API 응답 shape을 흉내낸 정적 스키마 — sync.py가 get_data_source로 property id를
    찾는 모든 지점(역방향 relation 개명, 정방향 relation 개명, 대시보드 위젯 축, 표 컬럼 순서)이
    데이터를 찾을 수 있도록 각 DB 종류가 갖는 속성을 전부 담아둔다."""
    if "Opportunity" in data_source_id:
        return {
            "properties": {
                "업무": {"id": "opp-title-prop-id", "type": "title"},
                "빈도": {"id": "freq-prop-id", "type": "select"},
                "적합성": {"id": "fitness-prop-id", "type": "select"},
                "Layer": {"id": "layer-prop-id", "type": "number"},
                "pivot 사유": {"id": "pivot-reason-prop-id", "type": "rich_text"},
                "Total Progress": {"id": "total-progress-prop-id", "type": "rollup"},
                "Related to Roadmap": {
                    "id": "auto-prop-id",
                    "type": "relation",
                    "relation": {"dual_property": {"synced_property_name": "Objective"}},
                },
                # 실제로는 위 "Related to Roadmap"이 개명되어 "Task"가 되지만, 이 fake는
                # PATCH 호출을 반영해 상태를 바꾸지 않는 정적 스키마라 개명 후 이름을 미리 같이 준다
                # (컬럼 순서 정렬 코드가 최종 이름 "Task"로 조회하므로).
                "Task": {"id": "auto-prop-id", "type": "relation"},
            }
        }
    if "팀원" in data_source_id:
        return {
            "properties": {
                "팀원": {"id": "team-title-prop-id", "type": "title"},
                "Task 진행률": {"id": "team-progress-prop-id", "type": "number"},
                "Related to Roadmap": {
                    "id": "auto-prop-id-2",
                    "type": "relation",
                    "relation": {"dual_property": {"synced_property_name": "담당자"}},
                },
            }
        }
    if "Roadmap" in data_source_id:
        return {
            "properties": {
                "Task": {"id": "roadmap-title-prop-id", "type": "title"},
                "주차": {"id": "week-prop-id", "type": "number"},
                "category": {"id": "category-prop-id", "type": "select"},
                "지표명": {"id": "metric-name-prop-id", "type": "rich_text"},
                "단위": {"id": "unit-prop-id", "type": "rich_text"},
                "기존값": {"id": "baseline-prop-id", "type": "number"},
                "현재값": {"id": "current-prop-id", "type": "number"},
                "목표값": {"id": "target-prop-id", "type": "number"},
                "Objective": {"id": "objective-prop-id", "type": "relation"},
                "업무": {"id": "objective-prop-id", "type": "relation"},
                "담당자": {"id": "member-relation-prop-id", "type": "relation"},
                "Progress": {"id": "progress-prop-id", "type": "formula"},
                "착수 여부": {"id": "started-prop-id", "type": "checkbox"},
            }
        }
    raise AssertionError(f"unexpected data_source_id in test fake: {data_source_id}")


def _patch_notion_api(monkeypatch):
    counter = _FakeCounter()
    calls = {
        "create_database": [],
        "create_database_row": [],
        "create_database_row_properties": [],
        "update_page_properties": [],
        "update_data_source_properties": [],
        "update_callout_text": [],
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
        return [{"id": "goal-callout-block"}, {"id": "divider-block"}]

    def fake_create_database_row(data_source_id, properties, headers, blocks=None):
        calls["create_database_row"].append(data_source_id)
        calls["create_database_row_properties"].append(properties)
        calls.setdefault("blocks", []).append(blocks)
        return {"id": counter.next("row"), "url": "https://notion.so/row"}

    def fake_update_page_properties(page_id, properties, headers):
        calls["update_page_properties"].append(page_id)

    def fake_get_data_source(data_source_id, headers):
        return _schema_for(data_source_id)

    def fake_update_data_source_properties(data_source_id, properties, headers):
        calls["update_data_source_properties"].append((data_source_id, properties))

    def fake_update_view_configuration(view_id, configuration, headers):
        calls.setdefault("update_view_configuration", []).append((view_id, configuration))

    def fake_update_view_sorts(view_id, sorts, headers):
        calls.setdefault("update_view_sorts", []).append((view_id, sorts))

    def fake_list_views(database_id, headers):
        calls.setdefault("list_views", []).append(database_id)
        return [{"object": "view", "id": f"table-view-{database_id}"}]

    def fake_update_callout_text(block_id, content, headers):
        calls["update_callout_text"].append((block_id, content))

    monkeypatch.setattr(sync_module, "create_page", fake_create_page)
    monkeypatch.setattr(sync_module, "create_database", fake_create_database)
    monkeypatch.setattr(sync_module, "get_block_children", fake_get_block_children)
    monkeypatch.setattr(sync_module, "create_database_row", fake_create_database_row)
    monkeypatch.setattr(sync_module, "update_page_properties", fake_update_page_properties)
    monkeypatch.setattr(sync_module, "get_data_source", fake_get_data_source)
    monkeypatch.setattr(sync_module, "update_data_source_properties", fake_update_data_source_properties)
    monkeypatch.setattr(sync_module, "update_view_configuration", fake_update_view_configuration)
    monkeypatch.setattr(sync_module, "update_view_sorts", fake_update_view_sorts)
    monkeypatch.setattr(sync_module, "list_views", fake_list_views)
    monkeypatch.setattr(sync_module, "update_callout_text", fake_update_callout_text)

    return calls


def test_progress_fraction_clamps_and_handles_equal_baseline_target():
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
    roadmap = _roadmap()
    roadmap.metrics = [
        Metric(task_id="task_001", metric_name="m", unit="분", baseline_value=100, current_value=50, target_value=0),
    ]
    roadmap.role_reassignment_suggestions = [
        RoleReassignmentSuggestion(task_id="task_001", assigned_member_ids=["M1", "M2"], reason="x"),
    ]

    result = sync_module._member_avg_progress(roadmap)

    assert result == {"M1": 0.5, "M2": 0.5}


def test_sync_roadmap_creates_databases_in_roadmap_first_order(session, monkeypatch):
    calls = _patch_notion_api(monkeypatch)

    workspace = sync_module.sync_roadmap(
        _goal(), _roadmap(), _onboarding(), "acc-1", "parent-page", session, {}
    )

    # QA_amendments 2절 배치 순서(목표 콜아웃 - 지표 대시보드 - Roadmap - Opportunity Map - 팀원 -
    # 성숙도 진단)를 만족하려면 블록이 이 순서로 페이지에 붙어야 하고, 블록은 생성 순서를 그대로
    # 따르므로 데이터베이스도 이 순서로 만들어야 한다.
    assert calls["create_database"] == ["Roadmap", "Opportunity Map", "팀원"]
    assert len(calls["create_database_row"]) == 3  # 팀원 1 + Opportunity Map 1 + Roadmap 1
    assert calls["update_page_properties"] == []

    assert get_work_item_page_id(session, "acc-1", "goal_001", "wi_001") is not None
    task_page_id = get_task_page_id(session, "acc-1", "goal_001", "task_001")
    assert task_page_id is not None
    assert workspace.roadmap_database_id.startswith("db-Roadmap")


def test_sync_roadmap_attaches_relations_after_all_three_databases_exist(session, monkeypatch):
    calls = _patch_notion_api(monkeypatch)

    sync_module.sync_roadmap(_goal(), _roadmap(), _onboarding(), "acc-1", "parent-page", session, {})

    # Roadmap 스키마 자체엔 relation이 없어서(테스트는 스키마 함수를 직접 검증하는 test_notion_schemas
    # 쪽에서 다룬다), 세 DB가 다 생긴 뒤 PATCH로 relation 두 개를 붙였는지만 여기서 확인한다.
    relation_patches = [
        props
        for (ds_id, props) in calls["update_data_source_properties"]
        if "Roadmap" in ds_id and "Objective" in props
    ]
    assert len(relation_patches) == 1
    assert relation_patches[0]["Objective"]["relation"]["data_source_id"].startswith("db-Opportunity")
    assert relation_patches[0]["담당자"]["relation"]["data_source_id"].startswith("db-팀원")


def test_sync_roadmap_renames_reverse_and_forward_relations_and_adds_progress_rollup(session, monkeypatch):
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

    # Roadmap 자신의 정방향 relation("Objective") -> "업무"로 개명 (QA_amendments 2절)
    roadmap_renames = [
        (ds_id, props)
        for ds_id, props in calls["update_data_source_properties"]
        if "Roadmap" in ds_id and any(v.get("name") == "업무" for v in props.values())
    ]
    assert len(roadmap_renames) == 1

    # Opportunity Map에 Total Progress rollup 추가
    rollup_calls = [
        (ds_id, props)
        for ds_id, props in calls["update_data_source_properties"]
        if "Total Progress" in props
    ]
    assert len(rollup_calls) == 1
    assert rollup_calls[0][1]["Total Progress"]["rollup"]["relation_property_name"] == "Task"
    assert rollup_calls[0][1]["Total Progress"]["rollup"]["rollup_property_name"] == "Progress"


def test_sync_roadmap_sets_dashboard_icon_cover_and_purple_goal_callout(session, monkeypatch):
    calls = _patch_notion_api(monkeypatch)

    sync_module.sync_roadmap(_goal("이번 목표는 이거예요"), _roadmap(), _onboarding(), "acc-1", "parent-page", session, {})

    assert calls["create_page_icon"] == ["🧭"]
    assert calls["create_page_cover_url"] == [sync_module._DASHBOARD_COVER_URL]
    assert "webb1.jpg" in sync_module._DASHBOARD_COVER_URL

    dashboard_blocks = calls["create_page_blocks"][0]
    goal_callout = dashboard_blocks[0]
    assert goal_callout["type"] == "callout"
    assert goal_callout["callout"]["color"] == "purple_background"
    assert goal_callout["callout"]["rich_text"][0]["text"]["content"] == "이번 목표는 이거예요"

    # 예전엔 있던 발견/적용 수 콜아웃 2개가 더 이상 없다 — 콜아웃 + 구분선 2블록뿐.
    assert len(dashboard_blocks) == 2


def test_sync_roadmap_updates_goal_callout_text_on_republish(session, monkeypatch):
    calls = _patch_notion_api(monkeypatch)

    sync_module.sync_roadmap(_goal("첫 목표"), _roadmap(), _onboarding(), "acc-1", "parent-page", session, {})
    sync_module.sync_roadmap(_goal("바뀐 목표"), _roadmap(), _onboarding(), "acc-1", "parent-page", session, {})

    # 워크스페이스는 최초 1번만 만들어지지만, 목표 콜아웃 텍스트는 발행마다 최신으로 갱신된다.
    assert calls["update_callout_text"] == [
        ("goal-callout-block", "첫 목표"),
        ("goal-callout-block", "바뀐 목표"),
    ]


def test_sync_roadmap_does_not_auto_create_any_chart_views(session, monkeypatch):
    """QA_amendments 2절 20번 지표 대시보드는 자동 생성 대상에서 뺐다(2026-07-15) — Notion
    "Dashboard" 뷰는 유료 플랜 전용이고, 대안으로 시도한 개별 chart 뷰는 사용자가 원한 "페이지
    맨 위 별도 섹션 2열 배치"를 낼 수 없어(그러려면 API가 지원하지 않는 linked database가
    필요) 억지로 비슷하게 만들지 않기로 했다 — 표 뷰(Table)만 남는다."""
    calls = _patch_notion_api(monkeypatch)

    sync_module.sync_roadmap(_goal(), _roadmap(), _onboarding(), "acc-1", "parent-page", session, {})

    chart_configs = [c for (_, c) in calls["update_view_configuration"] if c.get("type") == "chart"]
    assert chart_configs == []


def test_sync_roadmap_sets_table_column_order_for_roadmap_and_opportunity(session, monkeypatch):
    calls = _patch_notion_api(monkeypatch)

    sync_module.sync_roadmap(_goal(), _roadmap(), _onboarding(), "acc-1", "parent-page", session, {})

    table_configs = [
        (view_id, config)
        for (view_id, config) in calls["update_view_configuration"]
        if config.get("type") == "table"
    ]
    assert len(table_configs) == 2

    roadmap_view_id, roadmap_config = next((v, c) for v, c in table_configs if "Roadmap" in v)
    roadmap_ids_in_order = [p["property_id"] for p in roadmap_config["properties"]]
    assert roadmap_ids_in_order == [
        "week-prop-id",
        "category-prop-id",
        "roadmap-title-prop-id",
        "objective-prop-id",
        "started-prop-id",
        "progress-prop-id",
        "member-relation-prop-id",
        "metric-name-prop-id",
        "unit-prop-id",
        "baseline-prop-id",
        "current-prop-id",
        "target-prop-id",
    ]

    opportunity_view_id, opportunity_config = next((v, c) for v, c in table_configs if "Opportunity" in v)
    opportunity_ids_in_order = [p["property_id"] for p in opportunity_config["properties"]]
    assert opportunity_ids_in_order == [
        "opp-title-prop-id",
        "freq-prop-id",
        "fitness-prop-id",
        "layer-prop-id",
        "auto-prop-id",
        "total-progress-prop-id",
        "pivot-reason-prop-id",
    ]

    assert calls["update_view_sorts"] == [(opportunity_view_id, [{"property": "적합성", "direction": "ascending"}])]


def test_sync_roadmap_reuses_workspace_and_upserts_rows_on_second_call(session, monkeypatch):
    calls = _patch_notion_api(monkeypatch)

    sync_module.sync_roadmap(_goal(), _roadmap(), _onboarding(), "acc-1", "parent-page", session, {})
    sync_module.sync_roadmap(_goal(), _roadmap(), _onboarding(), "acc-1", "parent-page", session, {})

    # 워크스페이스(데이터베이스 3개)는 한 번만 만든다
    assert len(calls["create_database"]) == 3
    # 두 번째 호출은 같은 work_item_id/task_id/member_id라 새로 만들지 않고 갱신한다
    assert len(calls["create_database_row"]) == 3
    assert len(calls["update_page_properties"]) == 3


def test_sync_roadmap_writes_task_week_number(session, monkeypatch):
    calls = _patch_notion_api(monkeypatch)

    sync_module.sync_roadmap(_goal(), _roadmap(), _onboarding(), "acc-1", "parent-page", session, {})

    task_properties = calls["create_database_row_properties"][-1]
    assert task_properties[sync_module.ROADMAP_WEEK_PROP] == {"number": 1}


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


def _diagnosis() -> MaturityDiagnosis:
    return MaturityDiagnosis(
        goal_id="goal_001",
        axis_scores=[AxisScore(axis=axis, score=3, interpretation="보통") for axis in MATURITY_AXES],
        priority_axes=[MATURITY_AXES[0], MATURITY_AXES[1]],
        summary="아직 초기 단계예요",
    )


def test_sync_diagnosis_creates_maturity_database_lazily_and_appends_row(session, monkeypatch):
    calls = _patch_notion_api(monkeypatch)

    workspace = sync_module.sync_roadmap(
        _goal(), _roadmap(), _onboarding(), "acc-1", "parent-page", session, {}
    )
    assert workspace.maturity_database_id is None  # 진단 없이는 아직 안 만든다

    sync_module.sync_diagnosis(_diagnosis(), workspace, session, {})

    assert calls["create_database"][-1] == "AX 성숙도 진단"
    assert workspace.maturity_database_id is not None

    maturity_row_properties = calls["create_database_row_properties"][-1]
    assert maturity_row_properties[sync_module.MATURITY_SUMMARY_PROP] == {
        "rich_text": [{"type": "text", "text": {"content": "아직 초기 단계예요"}}]
    }
    for axis in MATURITY_AXES:
        assert maturity_row_properties[axis.value] == {"number": 3}

    reloaded = get_workspace(session, "acc-1")
    assert reloaded.maturity_database_id == workspace.maturity_database_id


def test_sync_diagnosis_appends_new_row_without_recreating_database(session, monkeypatch):
    calls = _patch_notion_api(monkeypatch)
    workspace = sync_module.sync_roadmap(
        _goal(), _roadmap(), _onboarding(), "acc-1", "parent-page", session, {}
    )

    sync_module.sync_diagnosis(_diagnosis(), workspace, session, {})
    maturity_db_count = calls["create_database"].count("AX 성숙도 진단")
    sync_module.sync_diagnosis(_diagnosis(), workspace, session, {})

    assert calls["create_database"].count("AX 성숙도 진단") == maturity_db_count == 1
    maturity_rows = [
        ds_id for ds_id in calls["create_database_row"] if ds_id == f"{workspace.maturity_database_id}-ds"
    ]
    assert len(maturity_rows) == 2
