from app.schemas.opportunity import OpportunityCard, ProductivityIncreaseResult


def calculate_time_saved(
    current_time_minutes: float,
    expected_time_saved_minutes: float | None = None,
    expected_reduction_rate: float | None = None,
) -> int:
    """Before(자가진단 소요시간) 대비 예상 절감 시간(분)을 계산한다."""
    if expected_time_saved_minutes is not None:
        return round(min(expected_time_saved_minutes, current_time_minutes))
    if expected_reduction_rate is not None:
        return round(current_time_minutes * expected_reduction_rate)
    raise ValueError(
        "expected_time_saved_minutes 또는 expected_reduction_rate 중 하나는 필요합니다"
    )


def calculate_ai_assistable_ratio(cards: list[OpportunityCard]) -> ProductivityIncreaseResult:
    """사용자의 전체 task 중 AI 활용 가능(is_ai_assistable) task 비율을 계산한다."""
    total = len(cards)
    if total == 0:
        raise ValueError("cards가 비어 있습니다")

    assistable = sum(1 for card in cards if card.metrics.is_ai_assistable)
    return ProductivityIncreaseResult(
        total_task_count=total,
        ai_assistable_task_count=assistable,
        ratio=round(assistable / total, 4),
    )
