"""
onboarding/answers.py

인터뷰 제출 원본(raw) 입력 스키마. 프론트가 `questions.py` 대본으로 받은 답을 담아 보낸다.
기능 1 내부 스키마이므로 contracts/(공동 소유)에 두지 않는다 — 공유되는 것은 산출물
`OnboardingData`뿐이다. `service.build_onboarding()`이 이 입력을 OnboardingData로 조립한다.

반복 업무는 두 방식 중 하나로 들어올 수 있다:
- `task_details`: 프론트가 이미 후속 질문(빈도/정형성/…)까지 받아 항목화한 확정 답변
- `day_narrative`: 자유서술만 있고 항목화 전 (→ extract.py가 후보를 뽑아 확인받는 흐름)
둘 다 있으면 `task_details`를 우선한다 (사용자가 확인한 값이므로).
"""

from pydantic import BaseModel, Field

from app.contracts.onboarding import (
    AiAdoptionLevel,
    RepetitiveTask,
    TeamMemberTag,
)


class InterviewAnswers(BaseModel):
    # 기본 정보
    industry: str | None = None
    team_size: int = Field(gt=0)
    work_categories: list[str] = Field(default_factory=list)

    # AI 활용 수준
    ai_adoption_level: AiAdoptionLevel = AiAdoptionLevel.NONE

    # 조직 환경
    has_ai_guideline: bool = False
    designated_ai_tools: list[str] = Field(default_factory=list)
    external_ai_allowed: bool = False
    ai_usage_variance: str = ""

    # 반복 업무 (둘 중 하나 이상)
    day_narrative: str = Field(
        default="", description="하루 업무 시간순 자유서술 (항목화 전)"
    )
    task_details: list[RepetitiveTask] = Field(
        default_factory=list, description="후속 질문까지 확정된 반복 업무 항목"
    )

    # 팀원 태깅 (선택)
    member_tags: list[TeamMemberTag] = Field(default_factory=list)
