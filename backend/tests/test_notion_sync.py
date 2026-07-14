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
    calls = {"create_database": [], "create_database_row": [], "update_page_properties": []}

    def fake_create_page(parent_page_id, title, blocks, headers):
        return {"id": counter.next("dash-page"), "url": "https://notion.so/dash-page"}

    def fake_create_database(parent_page_id, title, properties, headers):
        calls["create_database"].append(title)
        db_id = counter.next(f"db-{title}")
        return {"database_id": db_id, "data_source_id": f"{db_id}-ds"}

    def fake_get_block_children(block_id, headers):
        return [{"id": "discovered-block"}, {"id": "applied-block"}]

    def fake_create_database_row(data_source_id, properties, headers, blocks=None):
        calls["create_database_row"].append(data_source_id)
        return {"id": counter.next("row"), "url": "https://notion.so/row"}

    def fake_update_page_properties(page_id, properties, headers):
        calls["update_page_properties"].append(page_id)

    monkeypatch.setattr(sync_module, "create_page", fake_create_page)
    monkeypatch.setattr(sync_module, "create_database", fake_create_database)
    monkeypatch.setattr(sync_module, "get_block_children", fake_get_block_children)
    monkeypatch.setattr(sync_module, "create_database_row", fake_create_database_row)
    monkeypatch.setattr(sync_module, "update_page_properties", fake_update_page_properties)

    return calls


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


def test_sync_roadmap_reuses_workspace_and_upserts_rows_on_second_call(session, monkeypatch):
    calls = _patch_notion_api(monkeypatch)

    sync_module.sync_roadmap(_goal(), _roadmap(), _onboarding(), "acc-1", "parent-page", session, {})
    sync_module.sync_roadmap(_goal(), _roadmap(), _onboarding(), "acc-1", "parent-page", session, {})

    # 워크스페이스(데이터베이스 3개)는 한 번만 만든다
    assert len(calls["create_database"]) == 3
    # 두 번째 호출은 같은 work_item_id/task_id/member_id라 새로 만들지 않고 갱신한다
    assert len(calls["create_database_row"]) == 3
    assert len(calls["update_page_properties"]) == 3
