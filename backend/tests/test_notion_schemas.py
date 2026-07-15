from app.notion.schemas import (
    OPPORTUNITY_TASK_RELATION_PROP,
    ROADMAP_MEMBER_RELATION_PROP,
    ROADMAP_OBJECTIVE_RELATION_PROP,
    ROADMAP_STARTED_PROP,
    opportunity_progress_rollup_property,
    roadmap_properties_schema,
)


def test_roadmap_properties_schema_uses_dual_relations_and_checkbox_started_prop():
    schema = roadmap_properties_schema("opp-ds-1", "team-ds-1")

    objective = schema[ROADMAP_OBJECTIVE_RELATION_PROP]["relation"]
    assert objective["data_source_id"] == "opp-ds-1"
    assert "dual_property" in objective

    member = schema[ROADMAP_MEMBER_RELATION_PROP]["relation"]
    assert member["data_source_id"] == "team-ds-1"
    assert "dual_property" in member

    # rollup/formula는 차트 축으로 못 써서(실측 확인) 순수 checkbox로 둔다 — sync.py가 계산해 써넣음.
    assert schema[ROADMAP_STARTED_PROP] == {"checkbox": {}}


def test_opportunity_progress_rollup_property_references_task_relation_and_progress():
    prop = opportunity_progress_rollup_property(OPPORTUNITY_TASK_RELATION_PROP)

    rollup = prop["Total Progress"]["rollup"]
    assert rollup["relation_property_name"] == OPPORTUNITY_TASK_RELATION_PROP
    assert rollup["rollup_property_name"] == "Progress"
    assert rollup["function"] == "average"


def test_team_properties_schema_uses_plain_number_for_progress():
    from app.notion.schemas import TEAM_PROGRESS_PROP, team_properties_schema

    schema = team_properties_schema()

    # rollup이 아니라 순수 number — 차트 y축으로 쓰려면 rollup/formula가 아니어야 한다(실측 확인).
    assert schema[TEAM_PROGRESS_PROP] == {"number": {"format": "number"}}


def test_checkbox_value():
    from app.notion.schemas import checkbox_value

    assert checkbox_value(True) == {"checkbox": True}
    assert checkbox_value(False) == {"checkbox": False}
