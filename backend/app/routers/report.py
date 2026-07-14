"""브라우저 데모용 통합 엔드포인트 — 인터뷰 답변 하나로 1→2→3→4를 끝까지 돌려 JSON으로 돌려준다.

Notion 발행은 하지 않는다(DB·OAuth 불필요). 리서치 레이어(기능 3)는 계약 §2.4대로 서버 내부에서만
호출하고 클라이언트에 노출하지 않는다 — 응답에는 로드맵 결과만 담고 ResearchContext는 넣지 않는다.
"""

from fastapi import APIRouter
from pydantic import BaseModel

from app.contracts.goal import GoalDefinition
from app.contracts.maturity import MaturityDiagnosis
from app.contracts.onboarding import OnboardingData
from app.contracts.roadmap import RoadmapResult
from app.diagnosis import diagnose_and_set_goal
from app.onboarding import InterviewAnswers, build_onboarding
from app.research import run_research
from app.roadmap import generate_roadmap

router = APIRouter(prefix="/report", tags=["report"])


class FullReport(BaseModel):
    onboarding: OnboardingData
    maturity: MaturityDiagnosis
    goal: GoalDefinition
    roadmap: RoadmapResult


@router.post("/generate", response_model=FullReport)
def generate(answers: InterviewAnswers) -> FullReport:
    onboarding = build_onboarding(answers)          # 기능 1
    diag = diagnose_and_set_goal(onboarding)         # 기능 2
    research = run_research(diag.goal)               # 기능 3 (내부 전용)
    roadmap = generate_roadmap(diag.goal, research, onboarding)  # 기능 4
    return FullReport(
        onboarding=onboarding,
        maturity=diag.maturity,
        goal=diag.goal,
        roadmap=roadmap,
    )
