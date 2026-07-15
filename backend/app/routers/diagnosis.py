"""기능 2 — AX 성숙도 진단 및 목표 설정 HTTP 엔드포인트.

- POST /diagnosis/diagnose             : OnboardingData → 성숙도 진단 + 목표 정의서 (기능 3·4 입력)
- POST /diagnosis/publish-report       : 진단(+로드맵)을 한 노션 페이지에 발행
- POST /diagnosis/generate-and-publish : 온보딩 → 진단·목표 → 리서치 → 로드맵 → 노션 발행 (1→2→3→4 전체)

리서치 레이어(기능 3)는 계약 §2.4대로 클라이언트에 노출하지 않고 서버 내부에서만 호출한다.
"""

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.contracts.goal import GoalDefinition
from app.contracts.maturity import MaturityDiagnosis
from app.contracts.onboarding import OnboardingData
from app.contracts.roadmap import RoadmapResult
from app.diagnosis import DiagnosisResult, diagnose_and_set_goal
from app.notion.publish import publish_report
from app.research import run_research
from app.roadmap import generate_roadmap

router = APIRouter(prefix="/diagnosis", tags=["diagnosis"])


class PublishReportRequest(BaseModel):
    goal: GoalDefinition
    diagnosis: MaturityDiagnosis
    onboarding: OnboardingData
    roadmap: RoadmapResult | None = None
    account_id: str = "default"
    parent_page_id: str | None = None


class GenerateAndPublishRequest(BaseModel):
    onboarding: OnboardingData
    account_id: str = "default"
    parent_page_id: str | None = None


class PublishReportResponse(BaseModel):
    notion_url: str
    page_id: str


def _raise_publish_error(e: Exception) -> None:
    """Notion 발행 실패를 500 대신 원인이 보이는 상태로 바꾼다 — ValueError는 사용자가 고칠 수
    있는 상태(계정 미연결 등, 400), httpx.HTTPStatusError는 Notion API 자체가 거절한 요청(예:
    스키마 검증 실패, 502)이다. 두 경우 다 배포 환경에서 서버 로그 없이도 브라우저 Network 탭에서
    바로 원인을 볼 수 있게 한다(원래는 어떤 예외든 그냥 500으로 뭉개져 디버깅이 서버 로그
    접근 없이는 불가능했다)."""
    status = 400 if isinstance(e, ValueError) else 502
    raise HTTPException(status_code=status, detail=str(e)) from e


@router.post("/diagnose", response_model=DiagnosisResult)
def diagnose(onboarding: OnboardingData) -> DiagnosisResult:
    return diagnose_and_set_goal(onboarding)


@router.post("/publish-report", response_model=PublishReportResponse)
def publish(payload: PublishReportRequest) -> PublishReportResponse:
    research = run_research(payload.goal) if payload.roadmap is not None else None
    try:
        result = publish_report(
            goal=payload.goal,
            onboarding=payload.onboarding,
            account_id=payload.account_id,
            diagnosis=payload.diagnosis,
            roadmap=payload.roadmap,
            parent_page_id=payload.parent_page_id,
            research=research,
        )
    except (ValueError, httpx.HTTPStatusError) as e:
        _raise_publish_error(e)
    return PublishReportResponse(notion_url=result["url"], page_id=result["page_id"])


@router.post("/generate-and-publish", response_model=PublishReportResponse)
def generate_and_publish(payload: GenerateAndPublishRequest) -> PublishReportResponse:
    diag = diagnose_and_set_goal(payload.onboarding)
    research = run_research(diag.goal)
    roadmap = generate_roadmap(diag.goal, research, payload.onboarding)
    try:
        result = publish_report(
            goal=diag.goal,
            onboarding=payload.onboarding,
            account_id=payload.account_id,
            diagnosis=diag.maturity,
            roadmap=roadmap,
            parent_page_id=payload.parent_page_id,
            research=research,
        )
    except (ValueError, httpx.HTTPStatusError) as e:
        _raise_publish_error(e)
    return PublishReportResponse(notion_url=result["url"], page_id=result["page_id"])
