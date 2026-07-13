from app.contracts.goal import GoalDefinition, OrgConstraints
from app.contracts.research import Finding, ResearchContext, ResearchStatus, SourceType
from app.contracts.roadmap import (
    FitnessAssessment,
    Metric,
    RoadmapResult,
    RoleReassignmentSuggestion,
    Task,
)
from app.notion.blocks import render_roadmap_page_blocks


def _goal() -> GoalDefinition:
    return GoalDefinition(
        goal_id="goal_001",
        goal_text="팀 위키를 만들고 보고서 작성을 자동화한다",
        org_constraints=OrgConstraints(security_level="high"),
    )


def _task(**overrides) -> Task:
    defaults = dict(
        task_id="task_001",
        title="온보딩 문서 정리",
        layer=1,
        week=1,
        difficulty="쉬움",
        est_time="2시간",
        expected_effect="검색 시간 감소",
        tools_needed=["Copilot"],
        failure_risk="문서 최신화 누락 주의",
        source_refs=["F1"],
        detailed_guide="1. 첫 단계\n2. 둘째 단계",
    )
    defaults.update(overrides)
    return Task(**defaults)


def _roadmap(**overrides) -> RoadmapResult:
    defaults = dict(
        goal_id="goal_001",
        research_status=ResearchStatus.OK,
        fitness_assessment=[
            FitnessAssessment(
                task_candidate="월간 보고서 작성",
                matrix_position="자주+정형",
                verdict="Pivot",
                reason="규칙기반 자동화가 더 적합",
            )
        ],
        tasks=[_task()],
        metrics=[Metric(task_id="task_001", metric_name="검색 시간", baseline="10분", target="2분")],
        role_reassignment_suggestions=[
            RoleReassignmentSuggestion(task_id="task_001", suggested_member="member_a", reason="강점 일치")
        ],
    )
    defaults.update(overrides)
    return RoadmapResult(**defaults)


def _research() -> ResearchContext:
    return ResearchContext(
        goal_id="goal_001",
        retrieved_at="2026-07-11T10:00:00Z",
        status=ResearchStatus.OK,
        findings=[
            Finding(
                finding_id="F1",
                source_title="Copilot 위키 구축 사례",
                source_url="https://example.com/f1",
                source_type=SourceType.PRACTICE,
                summary="위키를 자동 갱신한 사례",
                relevant_method="자동 리프레시",
                metric_snippet="온보딩 질문 응답 시간 35% 감소",
            )
        ],
    )


def _flat_text(block: dict) -> str:
    t = block["type"]
    rt = block[t]["rich_text"]
    return "".join(span["text"]["content"] for span in rt)


def test_render_includes_intro_paragraph_first():
    layout = render_roadmap_page_blocks(_goal(), _roadmap())
    assert layout.blocks[0]["type"] == "paragraph"
    assert "팀 위키를 만들고" in _flat_text(layout.blocks[0])


def test_render_includes_table_of_contents_and_stats_callout():
    layout = render_roadmap_page_blocks(_goal(), _roadmap())
    assert any(b["type"] == "table_of_contents" for b in layout.blocks)
    assert layout.stats_block_index is not None
    stats_block = layout.blocks[layout.stats_block_index]
    assert stats_block["type"] == "callout"
    assert stats_block["callout"]["icon"]["emoji"] == "📊"
    assert "완료 0/1" in _flat_text(stats_block)


def test_render_includes_fitness_section():
    layout = render_roadmap_page_blocks(_goal(), _roadmap())
    heading_texts = [
        _flat_text(b) for b in layout.blocks if b["type"] == "heading_2"
    ]
    assert "이 업무들, AI로 풀어도 될까요?" in heading_texts
    assert "이번 로드맵" in heading_texts


def _get_task_block(layout, roadmap: RoadmapResult) -> dict:
    position = layout.task_positions["task_001"]
    top_block = layout.blocks[position.top_level_index]
    if not position.wrapped_in_column:
        return top_block
    left_column_children = top_block["column_list"]["children"][0]["column"]["children"]
    return left_column_children[0]


def test_task_with_metric_renders_as_two_columns_checkbox_and_metric_panel():
    roadmap = _roadmap()
    layout = render_roadmap_page_blocks(_goal(), roadmap, research=_research())
    position = layout.task_positions["task_001"]
    assert position.wrapped_in_column is True

    top_block = layout.blocks[position.top_level_index]
    assert top_block["type"] == "column_list"
    columns = top_block["column_list"]["children"]
    assert len(columns) == 2

    checkbox = columns[0]["column"]["children"][0]
    metric_panel = columns[1]["column"]["children"][0]

    assert checkbox["type"] == "to_do"
    summary = _flat_text(checkbox)
    assert "🟢" in summary
    assert "온보딩 문서 정리" in summary
    assert checkbox["to_do"]["checked"] is False

    assert metric_panel["type"] == "callout"
    assert metric_panel["callout"]["icon"]["emoji"] == "📈"
    assert "검색 시간" in _flat_text(metric_panel)
    assert "10분 → 2분" in _flat_text(metric_panel)


def test_task_without_metric_renders_as_plain_checkbox_not_columns():
    roadmap = _roadmap(metrics=[])
    layout = render_roadmap_page_blocks(_goal(), roadmap)
    position = layout.task_positions["task_001"]
    assert position.wrapped_in_column is False
    assert layout.blocks[position.top_level_index]["type"] == "to_do"


def test_checkbox_children_contain_effect_reassignment_guide_and_sources_but_not_metric():
    roadmap = _roadmap()
    layout = render_roadmap_page_blocks(_goal(), roadmap, research=_research())
    checkbox = _get_task_block(layout, roadmap)
    children = checkbox["to_do"]["children"]

    all_text = " ".join(_flat_text(b) for b in children)
    assert "검색 시간 감소" in all_text
    assert "member_a" in all_text
    assert "실제 배분은 팀장님이 판단해주세요" in all_text
    assert "첫 단계" in all_text
    assert "Copilot 위키 구축 사례" in all_text
    # 지표는 옆 컬럼에 있으므로 체크박스 안에는 없어야 함
    assert "10분 → 2분" not in all_text


def test_source_citation_links_to_source_url_and_includes_metric_snippet():
    roadmap = _roadmap()
    layout = render_roadmap_page_blocks(_goal(), roadmap, research=_research())
    checkbox = _get_task_block(layout, roadmap)
    children = checkbox["to_do"]["children"]

    bullets = [b for b in children if b["type"] == "bulleted_list_item"]
    assert len(bullets) == 1
    spans = bullets[0]["bulleted_list_item"]["rich_text"]

    title_span = spans[0]
    assert title_span["text"]["content"] == "Copilot 위키 구축 사례"
    assert title_span["text"]["link"]["url"] == "https://example.com/f1"

    full_text = "".join(s["text"]["content"] for s in spans)
    assert "위키를 자동 갱신한 사례" in full_text
    assert "온보딩 질문 응답 시간 35% 감소" in full_text


def test_source_citation_falls_back_to_bare_ref_when_finding_missing():
    task = _task(source_refs=["F999"])
    roadmap = _roadmap(tasks=[task])
    layout = render_roadmap_page_blocks(_goal(), roadmap, research=_research())
    checkbox = _get_task_block(layout, roadmap)
    bullets = [b for b in checkbox["to_do"]["children"] if b["type"] == "bulleted_list_item"]
    assert "(F999)" in _flat_text(bullets[0])


def test_render_adds_warning_callout_when_research_status_not_ok():
    roadmap = _roadmap(research_status=ResearchStatus.PARTIAL)
    layout = render_roadmap_page_blocks(_goal(), roadmap)
    warning_callouts = [
        b for b in layout.blocks if b["type"] == "callout" and b["callout"]["icon"]["emoji"] == "⚠️"
    ]
    assert len(warning_callouts) == 1


def test_render_omits_task_section_when_no_tasks():
    roadmap = _roadmap(tasks=[], metrics=[], role_reassignment_suggestions=[])
    layout = render_roadmap_page_blocks(_goal(), roadmap)
    heading_texts = [_flat_text(b) for b in layout.blocks if b["type"] == "heading_2"]
    assert "이번 로드맵" not in heading_texts
    assert layout.stats_block_index is None
    assert layout.task_positions == {}
    assert not any(b["type"] in ("to_do", "column_list") for b in layout.blocks)
