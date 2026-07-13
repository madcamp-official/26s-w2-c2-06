"""
roadmap/stage_a.py

Stage A — AI 적합성 판정 + 실행 전략 초안 생성 (DraftPlan). 검색하지 않는다 (SPRINT1_CONTRACT.md 2.1절).
"""

from google import genai

from app.contracts.goal import GoalDefinition
from app.contracts.onboarding import OnboardingData
from app.contracts.research import ResearchContext
from app.roadmap.draft_plan import DraftPlan
from app.roadmap.gemini_client import generate_structured
from app.roadmap.prompts import build_stage_a_prompt


def run_stage_a(
    client: genai.Client,
    goal: GoalDefinition,
    research: ResearchContext,
    onboarding: OnboardingData,
) -> DraftPlan:
    prompt = build_stage_a_prompt(goal, research, onboarding)
    draft = generate_structured(client, prompt, DraftPlan)
    return draft.model_copy(update={"goal_id": goal.goal_id})
