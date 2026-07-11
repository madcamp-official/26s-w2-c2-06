from app.schemas.bp_matching import BPMatchResult
from app.schemas.opportunity import OpportunityCard, OpportunityMetrics
from app.schemas.task_judgment import TaskJudgment
from app.services.metrics_calculator import calculate_time_saved


def format_opportunity_card(match_result: BPMatchResult, judgment: TaskJudgment) -> OpportunityCard:
    """RAG 매칭 결과(BPMatchResult)와 LLM 판정 결과(TaskJudgment)를 하나의
    Opportunity 카드로 합친다. RAG 호출/LLM 판정 로직은 여기서 수행하지 않는다."""
    if match_result.task_id != judgment.task_id:
        raise ValueError(
            f"task_id mismatch: match_result={match_result.task_id!r}, "
            f"judgment={judgment.task_id!r}"
        )

    time_saved_minutes = calculate_time_saved(
        current_time_minutes=judgment.current_time_minutes,
        expected_time_saved_minutes=judgment.expected_time_saved_minutes,
        expected_reduction_rate=judgment.expected_reduction_rate,
    )

    return OpportunityCard(
        task_name=judgment.task_name,
        category=judgment.category,
        layer=judgment.layer,
        recommendation_type=judgment.recommendation_type,
        matched_cases=match_result.matched_cases,
        prompt_or_guide=judgment.prompt_or_guide or "",
        metrics=OpportunityMetrics(
            time_saved_minutes_estimate=time_saved_minutes,
            is_ai_assistable=judgment.is_ai_assistable,
        ),
    )
