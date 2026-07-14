"""
roadmap/stage_b.py

Stage B — DraftPlan을 사용자 노출용 RoadmapResult로 구조화. 검색하지 않는다.
disclaimer/goal_id/research_status는 LLM 출력에 의존하지 않고 코드에서 강제한다
(SPEC.md 4.4 고정 문구 보장 방식에 대한 담당자 결정 — FEATURE4 문서 참고).
"""

from google import genai

from app.contracts.goal import GoalDefinition
from app.contracts.onboarding import OnboardingData
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
    onboarding: OnboardingData,
) -> RoadmapResult:
    prompt = build_stage_b_prompt(draft, goal, onboarding)
    result = generate_structured(client, prompt, RoadmapResult)

    result.goal_id = goal.goal_id
    result.research_status = research_status

    valid_member_ids = {m.member_id for m in onboarding.member_tags}
    for suggestion in result.role_reassignment_suggestions:
        suggestion.disclaimer = ROLE_REASSIGNMENT_DISCLAIMER
        # 온보딩에 실제로 없는 member_id는 LLM이 지어낸 것으로 간주하고 버린다.
        suggestion.assigned_member_ids = [
            member_id
            for member_id in suggestion.assigned_member_ids
            if member_id in valid_member_ids
        ]

    for metric in result.metrics:
        # 발행 시점엔 현재값을 갱신할 트래킹 기능이 아직 없어 기존값과 동일하게 시작한다.
        metric.current_value = metric.baseline_value

    # Stage B 프롬프트는 fitness_assessment를 다시 채우라고 지시하지 않지만, structured output은
    # 스키마 전체를 채우려 들기 때문에 Stage B가 work_item_id 등을 새로 지어낼 수 있다(실 호출로 확인:
    # wi_006처럼 Stage A가 부여하지 않은 값이 나온 적 있음). Stage A가 이미 코드로 검증한 값이 항상
    # 정본이므로 Stage B의 출력 여부와 무관하게 무조건 덮어쓴다.
    result.fitness_assessment = draft.fitness_judgments

    return result
