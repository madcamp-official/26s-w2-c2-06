from fastapi import APIRouter

from app.schemas.opportunity import FormatOpportunityRequest, OpportunityCard
from app.services.opportunity_formatter import format_opportunity_card

router = APIRouter(prefix="/opportunities", tags=["opportunities"])


@router.post("/format", response_model=OpportunityCard)
def format_opportunity(payload: FormatOpportunityRequest) -> OpportunityCard:
    return format_opportunity_card(payload.match_result, payload.judgment)
