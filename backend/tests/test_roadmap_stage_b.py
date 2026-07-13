import json
from pathlib import Path

from app.contracts.goal import GoalDefinition
from app.contracts.research import ResearchStatus
from app.contracts.roadmap import (
    ROLE_REASSIGNMENT_DISCLAIMER,
    FitnessAssessment,
    RoadmapResult,
    RoleReassignmentSuggestion,
)
from app.roadmap.draft_plan import DraftPlan
from app.roadmap.stage_b import run_stage_b
from tests.conftest import FakeClient

FIXTURES_DIR = Path(__file__).parent.parent / "app" / "fixtures"


def _load_goal() -> GoalDefinition:
    return GoalDefinition.model_validate(
        json.loads((FIXTURES_DIR / "goal_001.json").read_text())
    )


def test_run_stage_b_forces_goal_id_research_status_and_disclaimer():
    goal = _load_goal()
    draft = DraftPlan(goal_id=goal.goal_id, strategy_draft="s")

    llm_output = RoadmapResult(
        goal_id="wrong_id",
        research_status=ResearchStatus.OK,
        role_reassignment_suggestions=[
            RoleReassignmentSuggestion(
                task_id="task_001",
                suggested_member="member_a",
                reason="x",
                disclaimer="이상한 문구",
            )
        ],
    )
    client = FakeClient(parsed=llm_output)

    result = run_stage_b(client, draft, goal, research_status=ResearchStatus.PARTIAL)

    assert result.goal_id == goal.goal_id
    assert result.research_status == ResearchStatus.PARTIAL
    assert result.role_reassignment_suggestions[0].disclaimer == ROLE_REASSIGNMENT_DISCLAIMER


def test_run_stage_b_falls_back_to_draft_fitness_when_empty():
    goal = _load_goal()
    draft = DraftPlan(
        goal_id=goal.goal_id,
        strategy_draft="s",
        fitness_judgments=[
            FitnessAssessment(
                task_candidate="월간 보고서 작성",
                matrix_position="자주+정형",
                verdict="Pivot",
                reason="규칙기반 자동화 추천",
            )
        ],
    )
    llm_output = RoadmapResult(goal_id=goal.goal_id, research_status=ResearchStatus.OK)
    client = FakeClient(parsed=llm_output)

    result = run_stage_b(client, draft, goal, research_status=ResearchStatus.OK)

    assert len(result.fitness_assessment) == 1
    assert result.fitness_assessment[0].task_candidate == "월간 보고서 작성"
