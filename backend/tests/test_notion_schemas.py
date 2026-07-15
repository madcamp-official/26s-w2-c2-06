from app.notion.schemas import (
    OPPORTUNITY_TASK_RELATION_PROP,
    ROADMAP_MEMBER_RELATION_PROP,
    ROADMAP_OBJECTIVE_RELATION_PROP,
    ROADMAP_STARTED_PROP,
    ROADMAP_WEEK_PROP,
    opportunity_progress_rollup_property,
    roadmap_properties_schema,
    roadmap_relation_properties,
)


def test_roadmap_properties_schema_has_week_and_checkbox_started_prop_but_no_relations_yet():
    schema = roadmap_properties_schema()

    # Objective/담당자 relation은 Opportunity Map·팀원 DB가 아직 없는 시점에 만들어지는 스키마라
    # 여기 없다(sync.py가 DB 생성 순서를 뒤집어 Roadmap을 가장 먼저 만들기 때문 — QA_amendments 2절
    # 배치 순서). 대신 roadmap_relation_properties()로 따로 만든다(아래 테스트).
    assert ROADMAP_OBJECTIVE_RELATION_PROP not in schema
    assert ROADMAP_MEMBER_RELATION_PROP not in schema
    assert schema[ROADMAP_WEEK_PROP] == {"number": {"format": "number"}}
    # rollup/formula는 차트 축으로 못 써서(실측 확인) 순수 checkbox로 둔다 — sync.py가 계산해 써넣음.
    assert schema[ROADMAP_STARTED_PROP] == {"checkbox": {}}


def test_roadmap_relation_properties_uses_dual_relations():
    props = roadmap_relation_properties("opp-ds-1", "team-ds-1")

    objective = props[ROADMAP_OBJECTIVE_RELATION_PROP]["relation"]
    assert objective["data_source_id"] == "opp-ds-1"
    assert "dual_property" in objective

    member = props[ROADMAP_MEMBER_RELATION_PROP]["relation"]
    assert member["data_source_id"] == "team-ds-1"
    assert "dual_property" in member


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


def test_maturity_properties_schema_has_title_and_all_five_axes():
    from app.contracts.maturity import MATURITY_AXES
    from app.notion.schemas import (
        MATURITY_PRIORITY_PROP,
        MATURITY_SUMMARY_PROP,
        MATURITY_TITLE_PROP,
        maturity_properties_schema,
    )

    schema = maturity_properties_schema()

    assert schema[MATURITY_TITLE_PROP] == {"title": {}}
    assert schema[MATURITY_SUMMARY_PROP] == {"rich_text": {}}
    assert schema[MATURITY_PRIORITY_PROP] == {"rich_text": {}}
    for axis in MATURITY_AXES:
        assert schema[axis.value] == {"number": {"format": "number"}}
