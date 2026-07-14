import json
from pathlib import Path

from app.contracts.goal import GoalDefinition
from app.contracts.onboarding import OnboardingData
from app.contracts.research import ResearchContext
from app.contracts.roadmap import FitnessAssessment, FitnessVerdict, FrequencyBucket
from app.roadmap.draft_plan import DraftPlan
from app.roadmap.stage_a import run_stage_a
from tests.conftest import FakeClient

FIXTURES_DIR = Path(__file__).parent.parent / "app" / "fixtures"


def _load(name: str) -> dict:
    return json.loads((FIXTURES_DIR / name).read_text())


def test_run_stage_a_forces_goal_id_from_goal():
    goal = GoalDefinition.model_validate(_load("goal_001.json"))
    research = ResearchContext.model_validate(_load("research_context_goal_001.json"))
    onboarding = OnboardingData.model_validate(_load("onboarding_001.json"))

    llm_output = DraftPlan(
        goal_id="wrong_goal_id",
        fitness_judgments=[],
        strategy_draft="draft",
        task_outline=[],
        metric_ideas=[],
        reassignment_notes=[],
    )
    client = FakeClient(parsed=llm_output)

    draft = run_stage_a(client, goal, research, onboarding)

    assert draft.goal_id == "goal_001"
    assert len(client.models.calls) == 1


def test_run_stage_a_prompt_includes_goal_text():
    goal = GoalDefinition.model_validate(_load("goal_001.json"))
    research = ResearchContext.model_validate(_load("research_context_goal_001.json"))
    onboarding = OnboardingData.model_validate(_load("onboarding_001.json"))

    client = FakeClient(
        parsed=DraftPlan(goal_id=goal.goal_id, strategy_draft="s")
    )

    run_stage_a(client, goal, research, onboarding)

    prompt = client.models.calls[0]["contents"]
    assert goal.goal_text in prompt
    assert "F1" in prompt  # 리서치 finding_id 인용 가능해야 함
    assert "[wi_001]" in prompt  # 반복 업무 후보에 work_item 태그가 붙어야 함


def test_run_stage_a_forces_work_item_id_by_position_regardless_of_llm_output():
    goal = GoalDefinition.model_validate(_load("goal_001.json"))
    research = ResearchContext.model_validate(_load("research_context_goal_001.json"))
    onboarding = OnboardingData.model_validate(_load("onboarding_001.json"))

    llm_output = DraftPlan(
        goal_id=goal.goal_id,
        strategy_draft="draft",
        fitness_judgments=[
            FitnessAssessment(
                work_item_id="아무렇게나_지어낸_id",
                task_candidate="첫 번째 업무",
                matrix_position="자주+정형",
                fitness=FitnessVerdict.UNFIT,
                frequency_bucket=FrequencyBucket.WEEKLY,
                verdict="Pivot",
                reason="규칙기반 자동화 추천",
            ),
            FitnessAssessment(
                work_item_id="",
                task_candidate="두 번째 업무",
                matrix_position="자주+비정형",
                fitness=FitnessVerdict.FIT,
                layer=2,
                frequency_bucket=FrequencyBucket.DAILY,
                verdict="적합",
                reason="생성형 AI 최적",
            ),
        ],
    )
    client = FakeClient(parsed=llm_output)

    draft = run_stage_a(client, goal, research, onboarding)

    assert draft.fitness_judgments[0].work_item_id == "wi_001"
    assert draft.fitness_judgments[1].work_item_id == "wi_002"
