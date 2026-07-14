"""기능 1 — 온보딩 인터뷰 HTTP 엔드포인트.

- GET  /onboarding/interview      : 인터뷰 질문 대본 (프론트가 화면을 그릴 정적 데이터)
- POST /onboarding/extract-tasks  : 하루 업무 자유서술 → 반복 업무 후보 (사용자 확인용 초안, Gemini)
- POST /onboarding/submit         : 인터뷰 답변 → OnboardingData (기능 2·4 입력)
"""

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.contracts.onboarding import OnboardingData
from app.onboarding import InterviewAnswers, build_onboarding, extract_task_candidates
from app.onboarding.extract import TaskCandidate
from app.onboarding.questions import InterviewPart, get_interview_script
from app.core.gemini import get_client

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


class ExtractTasksRequest(BaseModel):
    day_narrative: str
    work_categories: list[str] = Field(default_factory=list)


class ExtractTasksResponse(BaseModel):
    tasks: list[TaskCandidate]


@router.get("/interview", response_model=list[InterviewPart])
def interview() -> list[InterviewPart]:
    return get_interview_script()


@router.post("/extract-tasks", response_model=ExtractTasksResponse)
def extract_tasks(payload: ExtractTasksRequest) -> ExtractTasksResponse:
    tasks = extract_task_candidates(
        get_client(), payload.day_narrative, payload.work_categories
    )
    return ExtractTasksResponse(tasks=tasks)


@router.post("/submit", response_model=OnboardingData)
def submit(answers: InterviewAnswers) -> OnboardingData:
    return build_onboarding(answers)
