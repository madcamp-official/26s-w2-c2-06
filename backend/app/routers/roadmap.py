from fastapi import APIRouter
from pydantic import BaseModel

from app.contracts.goal import GoalDefinition
from app.contracts.onboarding import OnboardingData
from app.contracts.research import ResearchContext
from app.contracts.roadmap import RoadmapResult
from app.roadmap import generate_roadmap

router = APIRouter(prefix="/roadmap", tags=["roadmap"])


class GenerateRoadmapRequest(BaseModel):
    goal: GoalDefinition
    research: ResearchContext
    onboarding: OnboardingData


@router.post("/generate", response_model=RoadmapResult)
def generate(payload: GenerateRoadmapRequest) -> RoadmapResult:
    return generate_roadmap(payload.goal, payload.research, payload.onboarding)
