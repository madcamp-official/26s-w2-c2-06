from fastapi import APIRouter
from pydantic import BaseModel

from app.contracts.goal import GoalDefinition
from app.contracts.onboarding import OnboardingData
from app.contracts.roadmap import RoadmapResult
from app.notion.progress import refresh_dashboard_stats
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


class RefreshProgressResponse(BaseModel):
    discovered: int
    total_work_items: int
    applied: int
    total_tasks: int


@router.post("/generate", response_model=RoadmapResult)
def generate(payload: GenerateRoadmapRequest) -> RoadmapResult:
    research = run_research(payload.goal)
    return generate_roadmap(payload.goal, research, payload.onboarding)


@router.post("/publish", response_model=PublishRoadmapResponse)
def publish(payload: PublishRoadmapRequest) -> PublishRoadmapResponse:
    # 리서치 레이어는 API에 비노출(계약 §2.4) — 인용 링크 렌더링을 위해 서버 내부에서만 재조회한다.
    # goal_id 캐싱(research/cache.py) 덕분에 이미 생성된 로드맵이면 재검색 비용이 거의 없다.
    research = run_research(payload.goal)
    result = publish_roadmap(
        payload.goal,
        payload.roadmap,
        payload.onboarding,
        payload.account_id,
        payload.parent_page_id,
        research,
    )
    return PublishRoadmapResponse(notion_url=result["url"], page_id=result["page_id"])


@router.post("/generate-and-publish", response_model=PublishRoadmapResponse)
def generate_and_publish(payload: GenerateAndPublishRequest) -> PublishRoadmapResponse:
    research = run_research(payload.goal)
    roadmap = generate_roadmap(payload.goal, research, payload.onboarding)
    result = publish_roadmap(
        payload.goal, roadmap, payload.onboarding, payload.account_id, payload.parent_page_id, research
    )
    return PublishRoadmapResponse(notion_url=result["url"], page_id=result["page_id"])


@router.post("/{account_id}/refresh-progress", response_model=RefreshProgressResponse)
def refresh(account_id: str) -> RefreshProgressResponse:
    """Opportunity Map/Roadmap 데이터베이스를 다시 읽어와 대시보드 집계 콜아웃을 갱신한다 (수동 호출)."""
    result = refresh_dashboard_stats(account_id)
    return RefreshProgressResponse(**result)
