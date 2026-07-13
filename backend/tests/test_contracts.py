"""공동 소유 스키마(app/contracts/) 검증. SPRINT1_CONTRACT.md 7.3절: run_research() 출력이
ResearchContext 검증을 통과하는지 상시 확인하는 테스트가 이 파일이다."""

import json
from pathlib import Path

from app.contracts.goal import GoalDefinition
from app.contracts.onboarding import OnboardingData
from app.contracts.research import ResearchContext, ResearchStatus
from app.contracts.roadmap import ROLE_REASSIGNMENT_DISCLAIMER, RoleReassignmentSuggestion

FIXTURES_DIR = Path(__file__).parent.parent / "app" / "fixtures"


def _load_fixture(name: str) -> dict:
    return json.loads((FIXTURES_DIR / name).read_text())


def test_goal_fixture_is_valid_goal_definition():
    goal = GoalDefinition.model_validate(_load_fixture("goal_001.json"))
    assert goal.goal_id == "goal_001"
    assert goal.org_constraints.security_level == "high"


def test_research_context_fixture_is_valid():
    research = ResearchContext.model_validate(_load_fixture("research_context_goal_001.json"))
    assert research.goal_id == "goal_001"
    assert research.status == ResearchStatus.OK
    assert 3 <= len(research.findings) <= 8


def test_onboarding_fixture_is_valid():
    onboarding = OnboardingData.model_validate(_load_fixture("onboarding_001.json"))
    assert onboarding.team_size > 0
    assert len(onboarding.repetitive_tasks) >= 1


def test_research_context_failed_status_allows_empty_findings():
    research = ResearchContext(
        goal_id="goal_001",
        retrieved_at="2026-07-11T10:00:00Z",
        status=ResearchStatus.FAILED,
        search_queries=["some query"],
        findings=[],
    )
    assert research.status == ResearchStatus.FAILED
    assert research.findings == []


def test_role_reassignment_suggestion_defaults_to_fixed_disclaimer():
    suggestion = RoleReassignmentSuggestion(
        task_id="task_001", suggested_member="member_a", reason="strength match"
    )
    assert suggestion.disclaimer == ROLE_REASSIGNMENT_DISCLAIMER
