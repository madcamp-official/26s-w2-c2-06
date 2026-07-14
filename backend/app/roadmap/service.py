"""
roadmap/service.py

기능 4 공개 진입점. SPRINT1_CONTRACT.md 2.3절에 고정된 함수 시그니처를 그대로 구현한다.
"""

from app.contracts.assets import AssetStore
from app.contracts.goal import GoalDefinition
from app.contracts.onboarding import OnboardingData
from app.contracts.research import ResearchContext
from app.contracts.roadmap import RoadmapResult
from app.roadmap.gemini_client import get_client
from app.roadmap.stage_a import run_stage_a
from app.roadmap.stage_b import run_stage_b


def generate_roadmap(
    goal: GoalDefinition,
    research: ResearchContext,
    onboarding: OnboardingData,
    assets: AssetStore | None = None,
) -> RoadmapResult:
    client = get_client()
    draft = run_stage_a(client, goal, research, onboarding)
    return run_stage_b(client, draft, goal, research.status, onboarding)
