import json
from pathlib import Path

from app.contracts.goal import GoalDefinition
from app.contracts.onboarding import OnboardingData, TeamMemberTag
from app.contracts.research import ResearchContext, ResearchStatus
from app.contracts.roadmap import (
    ROLE_REASSIGNMENT_DISCLAIMER,
    FitnessAssessment,
    FitnessVerdict,
    FrequencyBucket,
    RoadmapResult,
    RoleReassignmentSuggestion,
    Task,
    TaskCategory,
)
from app.roadmap.draft_plan import DraftPlan
from app.roadmap.stage_b import run_stage_b
from tests.conftest import FakeClient

FIXTURES_DIR = Path(__file__).parent.parent / "app" / "fixtures"


def _load_goal() -> GoalDefinition:
    return GoalDefinition.model_validate(
        json.loads((FIXTURES_DIR / "goal_001.json").read_text())
    )


def _onboarding_with_members(*member_ids: str) -> OnboardingData:
    return OnboardingData(
        team_size=max(len(member_ids), 1),
        member_tags=[
            TeamMemberTag(member_id=mid, ai_comfort_level="중간", workload_level="중간")
            for mid in member_ids
        ],
    )


def _load_research() -> ResearchContext:
    return ResearchContext.model_validate(
        json.loads((FIXTURES_DIR / "research_context_goal_001.json").read_text())
    )


def _research(status: ResearchStatus = ResearchStatus.OK) -> ResearchContext:
    research = _load_research()
    return research.model_copy(update={"status": status})


def test_run_stage_b_forces_goal_id_research_status_and_disclaimer():
    goal = _load_goal()
    draft = DraftPlan(goal_id=goal.goal_id, strategy_draft="s")

    llm_output = RoadmapResult(
        goal_id="wrong_id",
        research_status=ResearchStatus.OK,
        role_reassignment_suggestions=[
            RoleReassignmentSuggestion(
                task_id="task_001",
                assigned_member_ids=["M1"],
                reason="x",
                disclaimer="이상한 문구",
            )
        ],
    )
    client = FakeClient(parsed=llm_output)
    onboarding = _onboarding_with_members("M1")

    result = run_stage_b(client, draft, goal, research=_research(ResearchStatus.PARTIAL), onboarding=onboarding)

    assert result.goal_id == goal.goal_id
    assert result.research_status == ResearchStatus.PARTIAL
    assert result.role_reassignment_suggestions[0].disclaimer == ROLE_REASSIGNMENT_DISCLAIMER
    assert result.role_reassignment_suggestions[0].assigned_member_ids == ["M1"]


def test_run_stage_b_drops_member_ids_not_in_onboarding():
    goal = _load_goal()
    draft = DraftPlan(goal_id=goal.goal_id, strategy_draft="s")

    llm_output = RoadmapResult(
        goal_id=goal.goal_id,
        research_status=ResearchStatus.OK,
        role_reassignment_suggestions=[
            RoleReassignmentSuggestion(
                task_id="task_001", assigned_member_ids=["M1", "made_up_member"], reason="x"
            )
        ],
    )
    client = FakeClient(parsed=llm_output)
    onboarding = _onboarding_with_members("M1")

    result = run_stage_b(client, draft, goal, research=_research(), onboarding=onboarding)

    assert result.role_reassignment_suggestions[0].assigned_member_ids == ["M1"]


def test_run_stage_b_initializes_current_value_to_baseline():
    from app.contracts.roadmap import Metric

    goal = _load_goal()
    draft = DraftPlan(goal_id=goal.goal_id, strategy_draft="s")

    llm_output = RoadmapResult(
        goal_id=goal.goal_id,
        research_status=ResearchStatus.OK,
        metrics=[
            Metric(
                task_id="task_001",
                metric_name="소요시간",
                unit="분",
                baseline_value=180,
                current_value=999,
                target_value=30,
            )
        ],
    )
    client = FakeClient(parsed=llm_output)
    onboarding = _onboarding_with_members()

    result = run_stage_b(client, draft, goal, research=_research(), onboarding=onboarding)

    assert result.metrics[0].current_value == 180


def test_run_stage_b_always_uses_stage_a_fitness_even_when_llm_returns_its_own():
    goal = _load_goal()
    draft = DraftPlan(
        goal_id=goal.goal_id,
        strategy_draft="s",
        fitness_judgments=[
            FitnessAssessment(
                work_item_id="wi_001",
                task_candidate="월간 보고서 작성",
                matrix_position="자주+정형",
                fitness=FitnessVerdict.UNFIT,
                frequency_bucket=FrequencyBucket.WEEKLY,
                verdict="Pivot",
                reason="규칙기반 자동화 추천",
            )
        ],
    )
    # structured output은 스키마 전체를 채우려 들어서 Stage B가 요청하지 않은 fitness_assessment도
    # 스스로 지어낼 수 있다(실 라이브 호출로 확인된 사례) — 이 경우에도 Stage A 값이 이겨야 한다.
    llm_output = RoadmapResult(
        goal_id=goal.goal_id,
        research_status=ResearchStatus.OK,
        fitness_assessment=[
            FitnessAssessment(
                work_item_id="wi_999_지어낸_값",
                task_candidate="LLM이 지어낸 업무",
                matrix_position="자주+비정형",
                fitness=FitnessVerdict.FIT,
                layer=1,
                frequency_bucket=FrequencyBucket.DAILY,
                verdict="적합",
                reason="지어낸 이유",
            )
        ],
    )
    client = FakeClient(parsed=llm_output)
    onboarding = _onboarding_with_members()

    result = run_stage_b(client, draft, goal, research=_research(), onboarding=onboarding)

    assert len(result.fitness_assessment) == 1
    assert result.fitness_assessment[0].task_candidate == "월간 보고서 작성"
    assert result.fitness_assessment[0].work_item_id == "wi_001"


def test_run_stage_b_fills_empty_source_refs_with_keyword_fallback():
    """gemini-3.1-flash-lite가 source_refs를 비워 응답하는 경우를 대비한 폴백 —
    task와 finding 텍스트의 키워드 겹침으로 가장 관련 있는 finding을 대신 채운다."""
    goal = _load_goal()
    draft = DraftPlan(goal_id=goal.goal_id, strategy_draft="s")
    llm_output = RoadmapResult(
        goal_id=goal.goal_id,
        research_status=ResearchStatus.OK,
        tasks=[
            Task(
                task_id="task_001",
                title="팀 위키 초안 작성",
                layer=2,
                week=1,
                category=TaskCategory.KNOWLEDGE,
                difficulty="쉬움",
                est_time="2시간",
                expected_effect="온보딩 문서 위키로 정리",
                tools_needed=["Copilot"],
                failure_risk="문서 최신화 누락",
                source_refs=[],
            )
        ],
    )
    client = FakeClient(parsed=llm_output)
    onboarding = _onboarding_with_members()

    result = run_stage_b(client, draft, goal, research=_research(), onboarding=onboarding)

    valid_ids = {f.finding_id for f in _research().findings}
    assert result.tasks[0].source_refs
    assert set(result.tasks[0].source_refs) <= valid_ids


def test_run_stage_b_keeps_empty_source_refs_when_no_keyword_overlap():
    goal = _load_goal()
    draft = DraftPlan(goal_id=goal.goal_id, strategy_draft="s")
    llm_output = RoadmapResult(
        goal_id=goal.goal_id,
        research_status=ResearchStatus.OK,
        tasks=[
            Task(
                task_id="task_001",
                title="사내 행사 다과 주문",
                layer=1,
                week=1,
                category=TaskCategory.CULTURE,
                difficulty="쉬움",
                est_time="30분",
                expected_effect="행사 준비 시간 단축",
                tools_needed=[],
                failure_risk="주문 누락",
                source_refs=[],
            )
        ],
    )
    client = FakeClient(parsed=llm_output)
    onboarding = _onboarding_with_members()

    result = run_stage_b(client, draft, goal, research=_research(), onboarding=onboarding)

    assert result.tasks[0].source_refs == []
