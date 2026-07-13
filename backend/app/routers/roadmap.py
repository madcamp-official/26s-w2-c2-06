from fastapi import APIRouter
from pydantic import BaseModel

from app.contracts.goal import GoalDefinition
from app.contracts.onboarding import OnboardingData
from app.contracts.roadmap import RoadmapResult
from app.notion.progress import refresh_progress
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
    account_id: str = "default"
    parent_page_id: str | None = None


class GenerateAndPublishRequest(GenerateRoadmapRequest):
    account_id: str = "default"


class PublishRoadmapResponse(BaseModel):
    notion_url: str
    page_id: str


class RefreshProgressResponse(BaseModel):
    completed: int
    total: int
    completed_task_titles: list[str]


@router.post("/generate", response_model=RoadmapResult)
def generate(payload: GenerateRoadmapRequest) -> RoadmapResult:
    research = run_research(payload.goal)
    return generate_roadmap(payload.goal, research, payload.onboarding)


@router.post("/publish", response_model=PublishRoadmapResponse)
def publish(payload: PublishRoadmapRequest) -> PublishRoadmapResponse:
    research = run_research(payload.goal)
    result = publish_roadmap(
        payload.goal, payload.roadmap, payload.account_id, research, payload.parent_page_id
    )
    return PublishRoadmapResponse(notion_url=result["url"], page_id=result["page_id"])


@router.post("/generate-and-publish", response_model=PublishRoadmapResponse)
def generate_and_publish(payload: GenerateAndPublishRequest) -> PublishRoadmapResponse:
    research = run_research(payload.goal)
    roadmap = generate_roadmap(payload.goal, research, payload.onboarding)
    result = publish_roadmap(payload.goal, roadmap, payload.account_id, research)
    return PublishRoadmapResponse(notion_url=result["url"], page_id=result["page_id"])


@router.post("/{page_id}/refresh-progress", response_model=RefreshProgressResponse)
def refresh(page_id: str) -> RefreshProgressResponse:
    """Notion에서 체크박스 상태를 다시 읽어와 페이지 안의 진행 현황 요약을 갱신한다 (수동 호출)."""
    result = refresh_progress(page_id)
    return RefreshProgressResponse(**result)
