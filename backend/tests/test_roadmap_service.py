import json
from pathlib import Path

import app.roadmap.service as service_module
from app.contracts.goal import GoalDefinition
from app.contracts.onboarding import OnboardingData
from app.contracts.research import ResearchContext
from app.contracts.roadmap import RoadmapResult
from app.roadmap.draft_plan import DraftPlan
from app.roadmap.service import generate_roadmap

FIXTURES_DIR = Path(__file__).parent.parent / "app" / "fixtures"


def _load(name: str) -> dict:
    return json.loads((FIXTURES_DIR / name).read_text())


def test_generate_roadmap_orchestrates_stage_a_then_stage_b(monkeypatch):
    goal = GoalDefinition.model_validate(_load("goal_001.json"))
    research = ResearchContext.model_validate(_load("research_context_goal_001.json"))
    onboarding = OnboardingData.model_validate(_load("onboarding_001.json"))

    calls = []
    fake_draft = DraftPlan(goal_id=goal.goal_id, strategy_draft="draft")
    fake_result = RoadmapResult(goal_id=goal.goal_id, research_status=research.status)

    def fake_get_client():
        calls.append("get_client")
        return "fake-client"

    def fake_run_stage_a(client, g, r, o):
        calls.append(("stage_a", client, g.goal_id, r.goal_id, o.team_size))
        return fake_draft

    def fake_run_stage_b(client, draft, g, research_status):
        calls.append(("stage_b", client, draft is fake_draft, g.goal_id, research_status))
        return fake_result

    monkeypatch.setattr(service_module, "get_client", fake_get_client)
    monkeypatch.setattr(service_module, "run_stage_a", fake_run_stage_a)
    monkeypatch.setattr(service_module, "run_stage_b", fake_run_stage_b)

    result = generate_roadmap(goal, research, onboarding)

    assert result is fake_result
    assert calls[0] == "get_client"
    assert calls[1] == ("stage_a", "fake-client", goal.goal_id, research.goal_id, onboarding.team_size)
    assert calls[2] == ("stage_b", "fake-client", True, goal.goal_id, research.status)
