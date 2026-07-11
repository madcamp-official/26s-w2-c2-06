import pytest

from app.schemas.bp_matching import DUMMY_MATCH_RESULT
from app.schemas.task_judgment import DUMMY_JUDGMENT, RecommendationType
from app.services.opportunity_formatter import format_opportunity_card


def test_format_opportunity_card_maps_fields():
    card = format_opportunity_card(DUMMY_MATCH_RESULT, DUMMY_JUDGMENT)

    assert card.task_name == DUMMY_JUDGMENT.task_name
    assert card.category == "문서작성"
    assert card.layer == 2
    assert card.recommendation_type == RecommendationType.WORKFLOW
    assert card.matched_cases == DUMMY_MATCH_RESULT.matched_cases
    assert card.prompt_or_guide == DUMMY_JUDGMENT.prompt_or_guide
    assert card.metrics.time_saved_minutes_estimate == 45
    assert card.metrics.is_ai_assistable is True


def test_format_opportunity_card_raises_on_task_id_mismatch():
    mismatched_judgment = DUMMY_JUDGMENT.model_copy(update={"task_id": "task_9999"})
    with pytest.raises(ValueError):
        format_opportunity_card(DUMMY_MATCH_RESULT, mismatched_judgment)


def test_format_opportunity_card_defaults_missing_guide_to_empty_string():
    judgment = DUMMY_JUDGMENT.model_copy(update={"prompt_or_guide": None})
    card = format_opportunity_card(DUMMY_MATCH_RESULT, judgment)
    assert card.prompt_or_guide == ""


def test_format_opportunity_card_uses_reduction_rate_when_no_direct_estimate():
    judgment = DUMMY_JUDGMENT.model_copy(
        update={"expected_time_saved_minutes": None, "expected_reduction_rate": 0.3}
    )
    card = format_opportunity_card(DUMMY_MATCH_RESULT, judgment)
    assert card.metrics.time_saved_minutes_estimate == 27
