"""
roadmap/service.py

기능 4 공개 진입점. SPRINT1_CONTRACT.md 2.3절에 고정된 함수 시그니처를 그대로 구현한다.
동일 goal_id 재요청은 캐시로 응답해 Gemini Stage A+B 재호출을 건너뛴다 (cache.py 참고).
"""

from app.contracts.assets import AssetStore
from app.contracts.goal import GoalDefinition
from app.contracts.onboarding import OnboardingData
from app.contracts.research import ResearchContext
from app.contracts.roadmap import RoadmapResult
from app.roadmap import cache
from app.roadmap.gemini_client import get_client
from app.roadmap.stage_a import run_stage_a
from app.roadmap.stage_b import run_stage_b


def generate_roadmap(
    goal: GoalDefinition,
    research: ResearchContext,
    onboarding: OnboardingData,
    assets: AssetStore | None = None,
) -> RoadmapResult:
    cached = cache.get(goal.goal_id)
    if cached is not None:
        return cached

    client = get_client()
    draft = run_stage_a(client, goal, research, onboarding)
    result = run_stage_b(client, draft, goal, research.status)

    cache.set(goal.goal_id, result)
    return result
