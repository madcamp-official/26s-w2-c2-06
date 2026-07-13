"""
roadmap/stage_b.py

Stage B — DraftPlan을 사용자 노출용 RoadmapResult로 구조화. 검색하지 않는다.
disclaimer/goal_id/research_status는 LLM 출력에 의존하지 않고 코드에서 강제한다
(SPEC.md 4.4 고정 문구 보장 방식에 대한 담당자 결정 — FEATURE4 문서 참고).
"""

from google import genai

from app.contracts.goal import GoalDefinition
from app.contracts.research import ResearchStatus
from app.contracts.roadmap import ROLE_REASSIGNMENT_DISCLAIMER, RoadmapResult
from app.roadmap.draft_plan import DraftPlan
from app.roadmap.gemini_client import generate_structured
from app.roadmap.prompts import build_stage_b_prompt


def run_stage_b(
    client: genai.Client,
    draft: DraftPlan,
    goal: GoalDefinition,
    research_status: ResearchStatus,
) -> RoadmapResult:
    prompt = build_stage_b_prompt(draft, goal)
    result = generate_structured(client, prompt, RoadmapResult)

    result.goal_id = goal.goal_id
    result.research_status = research_status
    for suggestion in result.role_reassignment_suggestions:
        suggestion.disclaimer = ROLE_REASSIGNMENT_DISCLAIMER
    if not result.fitness_assessment:
        result.fitness_assessment = draft.fitness_judgments

    return result
