import json
from pathlib import Path

from app.contracts.goal import GoalDefinition
from app.contracts.onboarding import OnboardingData
from app.contracts.research import ResearchContext
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
