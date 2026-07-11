import pytest

from app.schemas.bp_matching import DUMMY_MATCH_RESULT
from app.schemas.opportunity import OpportunityCard, OpportunityMetrics
from app.schemas.task_judgment import RecommendationType
from app.services.metrics_calculator import (
    calculate_ai_assistable_ratio,
    calculate_time_saved,
)


def _make_card(is_ai_assistable: bool) -> OpportunityCard:
    return OpportunityCard(
        task_name="더미 task",
        category="문서작성",
        layer=1,
        recommendation_type=RecommendationType.WORKFLOW,
        matched_cases=DUMMY_MATCH_RESULT.matched_cases,
        prompt_or_guide="",
        metrics=OpportunityMetrics(
            time_saved_minutes_estimate=10,
            is_ai_assistable=is_ai_assistable,
        ),
    )


class TestCalculateTimeSaved:
    def test_uses_direct_minutes_when_given(self):
        assert calculate_time_saved(90, expected_time_saved_minutes=45) == 45

    def test_caps_direct_minutes_at_current_time(self):
        assert calculate_time_saved(30, expected_time_saved_minutes=45) == 30

    def test_uses_reduction_rate_when_no_direct_minutes(self):
        assert calculate_time_saved(90, expected_reduction_rate=0.5) == 45

    def test_raises_when_neither_given(self):
        with pytest.raises(ValueError):
            calculate_time_saved(90)


class TestCalculateAiAssistableRatio:
    def test_computes_ratio(self):
        cards = [_make_card(True), _make_card(True), _make_card(False), _make_card(False)]
        result = calculate_ai_assistable_ratio(cards)
        assert result.total_task_count == 4
        assert result.ai_assistable_task_count == 2
        assert result.ratio == 0.5

    def test_raises_on_empty_list(self):
        with pytest.raises(ValueError):
            calculate_ai_assistable_ratio([])
