from fastapi import APIRouter
from pydantic import BaseModel

from app.contracts.goal import GoalDefinition
from app.contracts.onboarding import OnboardingData
from app.contracts.research import ResearchContext
from app.contracts.roadmap import RoadmapResult
from app.notion.publish import publish_roadmap
from app.roadmap import generate_roadmap

router = APIRouter(prefix="/roadmap", tags=["roadmap"])


class GenerateRoadmapRequest(BaseModel):
    goal: GoalDefinition
    research: ResearchContext
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


@router.post("/generate", response_model=RoadmapResult)
def generate(payload: GenerateRoadmapRequest) -> RoadmapResult:
    return generate_roadmap(payload.goal, payload.research, payload.onboarding)


@router.post("/publish", response_model=PublishRoadmapResponse)
def publish(payload: PublishRoadmapRequest) -> PublishRoadmapResponse:
    url = publish_roadmap(payload.goal, payload.roadmap, payload.account_id, payload.parent_page_id)
    return PublishRoadmapResponse(notion_url=url)


@router.post("/generate-and-publish", response_model=PublishRoadmapResponse)
def generate_and_publish(payload: GenerateAndPublishRequest) -> PublishRoadmapResponse:
    roadmap = generate_roadmap(payload.goal, payload.research, payload.onboarding)
    url = publish_roadmap(payload.goal, roadmap, payload.account_id)
    return PublishRoadmapResponse(notion_url=url)
