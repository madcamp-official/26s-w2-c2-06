import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.contracts.goal import GoalDefinition
from app.contracts.onboarding import OnboardingData
from app.contracts.roadmap import RoadmapResult
from app.notion.publish import publish_roadmap
from app.research import run_research
from app.roadmap import generate_roadmap

router = APIRouter(prefix="/roadmap", tags=["roadmap"])


class GenerateRoadmapRequest(BaseModel):
    goal: GoalDefinition
    onboarding: OnboardingData


class PublishRoadmapRequest(BaseModel):
    goal: GoalDefinition
    roadmap: RoadmapResult
    onboarding: OnboardingData
    account_id: str = "default"
    parent_page_id: str | None = None


class GenerateAndPublishRequest(GenerateRoadmapRequest):
    account_id: str = "default"
    parent_page_id: str | None = None


class PublishRoadmapResponse(BaseModel):
    notion_url: str
    page_id: str


def _raise_publish_error(e: Exception) -> None:
    """Notion 발행 실패를 500 대신 원인이 보이는 상태로 바꾼다 — ValueError는 사용자가 고칠 수
    있는 상태(계정 미연결 등, 400), httpx.HTTPStatusError는 Notion API 자체가 거절한 요청(예:
    스키마 검증 실패, 502)이다. 두 경우 다 배포 환경에서 서버 로그 없이도 브라우저 Network 탭에서
    바로 원인을 볼 수 있게 한다."""
    status = 400 if isinstance(e, ValueError) else 502
    raise HTTPException(status_code=status, detail=str(e)) from e


@router.post("/generate", response_model=RoadmapResult)
def generate(payload: GenerateRoadmapRequest) -> RoadmapResult:
    research = run_research(payload.goal)
    return generate_roadmap(payload.goal, research, payload.onboarding)


@router.post("/publish", response_model=PublishRoadmapResponse)
def publish(payload: PublishRoadmapRequest) -> PublishRoadmapResponse:
    # 리서치 레이어는 API에 비노출(계약 §2.4) — 인용 링크 렌더링을 위해 서버 내부에서만 재조회한다.
    # goal_id 캐싱(research/cache.py) 덕분에 이미 생성된 로드맵이면 재검색 비용이 거의 없다.
    research = run_research(payload.goal)
    try:
        result = publish_roadmap(
            payload.goal,
            payload.roadmap,
            payload.onboarding,
            payload.account_id,
            payload.parent_page_id,
            research,
        )
    except (ValueError, httpx.HTTPStatusError) as e:
        _raise_publish_error(e)
    return PublishRoadmapResponse(notion_url=result["url"], page_id=result["page_id"])


@router.post("/generate-and-publish", response_model=PublishRoadmapResponse)
def generate_and_publish(payload: GenerateAndPublishRequest) -> PublishRoadmapResponse:
    research = run_research(payload.goal)
    roadmap = generate_roadmap(payload.goal, research, payload.onboarding)
    try:
        result = publish_roadmap(
            payload.goal, roadmap, payload.onboarding, payload.account_id, payload.parent_page_id, research
        )
    except (ValueError, httpx.HTTPStatusError) as e:
        _raise_publish_error(e)
    return PublishRoadmapResponse(notion_url=result["url"], page_id=result["page_id"])
