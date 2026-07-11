from pydantic import BaseModel

from app.schemas.bp_matching import BPMatchCase, BPMatchResult
from app.schemas.task_judgment import RecommendationType, TaskJudgment


class OpportunityMetrics(BaseModel):
    time_saved_minutes_estimate: int
    is_ai_assistable: bool


class OpportunityCard(BaseModel):
    task_name: str
    category: str
    layer: int
    recommendation_type: RecommendationType
    matched_cases: list[BPMatchCase]
    prompt_or_guide: str
    metrics: OpportunityMetrics


class FormatOpportunityRequest(BaseModel):
    """POST /opportunities/format 요청 바디. RAG 매칭 결과와 LLM 판정 결과를 함께 받는다."""

    match_result: BPMatchResult
    judgment: TaskJudgment


class ProductivityIncreaseResult(BaseModel):
    total_task_count: int
    ai_assistable_task_count: int
    ratio: float
