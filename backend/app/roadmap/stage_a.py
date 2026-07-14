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

    # work_item_id는 LLM이 지어내지 않고, 프롬프트가 [wi_xxx]로 부여한 순서를 코드가 재확정한다
    # (fitness_judgments는 반복 업무 후보와 1:1·순서 보존이라는 프롬프트 지시에 의존).
    for i, judgment in enumerate(draft.fitness_judgments):
        judgment.work_item_id = f"wi_{i + 1:03d}"

    return draft.model_copy(update={"goal_id": goal.goal_id})
