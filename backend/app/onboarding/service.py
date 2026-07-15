"""
onboarding/service.py

기능 1 공개 진입점. 인터뷰 원본 답변(InterviewAnswers)을 산출물 OnboardingData로 조립한다.
이 출력이 기능 2(성숙도 진단·목표 설정)와 기능 4(로드맵 생성)의 입력이 된다 (SPEC 4.1).

조립은 규칙 기반(결정론적)이다 — LLM은 자유서술에서 업무 후보를 뽑을 때만 쓴다(extract.py).
"""

from google import genai

from app.contracts.onboarding import OnboardingData, OrgEnvironment, RepetitiveTask
from app.core.gemini import get_client
from app.onboarding.answers import InterviewAnswers
from app.onboarding.extract import TaskCandidate, extract_task_candidates


def _candidate_to_task(c: TaskCandidate) -> RepetitiveTask:
    return RepetitiveTask(
        title=c.title,
        frequency=c.frequency,
        is_standardized=c.is_standardized,
        avg_time_minutes=c.avg_time_minutes,
        contains_sensitive_info=c.contains_sensitive_info,
        current_method=c.current_method or "(미확인)",
    )


def _resolve_repetitive_tasks(
    answers: InterviewAnswers, client: genai.Client | None
) -> list[RepetitiveTask]:
    # 사용자가 후속 질문까지 확정한 항목이 있으면 그걸 우선한다.
    if answers.task_details:
        return answers.task_details
    # 아니면 자유서술에서 후보를 뽑아 채운다 (best-guess — 이후 재확인 권장).
    if answers.day_narrative.strip():
        gemini = client or get_client()
        candidates = extract_task_candidates(
            gemini, answers.day_narrative, answers.work_categories
        )
        return [_candidate_to_task(c) for c in candidates]
    return []


def build_onboarding(
    answers: InterviewAnswers, client: genai.Client | None = None
) -> OnboardingData:
    return OnboardingData(
        team_size=answers.team_size,
        industry=answers.industry,
        work_categories=answers.work_categories,
        ai_adoption_level=answers.ai_adoption_level,
        org_environment=OrgEnvironment(
            has_ai_guideline=answers.has_ai_guideline,
            designated_ai_tools=[t for t in answers.designated_ai_tools if t and t != "없음"],
            erp_data_integrated=answers.erp_data_integrated,
            external_ai_allowed=answers.external_ai_allowed,
            ai_usage_variance=answers.ai_usage_variance,
        ),
        repetitive_tasks=_resolve_repetitive_tasks(answers, client),
        member_tags=answers.member_tags,
    )
