from app.contracts.goal import GoalDefinition, OrgConstraints
from app.contracts.research import ResearchStatus
from app.contracts.roadmap import (
    FitnessAssessment,
    Metric,
    RoadmapResult,
    RoleReassignmentSuggestion,
    Task,
)
from app.notion.blocks import render_roadmap_blocks


def _goal() -> GoalDefinition:
    return GoalDefinition(
        goal_id="goal_001",
        goal_text="팀 위키를 만들고 보고서 작성을 자동화한다",
        org_constraints=OrgConstraints(security_level="high"),
    )


def _full_roadmap() -> RoadmapResult:
    return RoadmapResult(
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
        tasks=[
            Task(
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
            )
        ],
        role_reassignment_suggestions=[
            RoleReassignmentSuggestion(
                task_id="task_001", suggested_member="member_a", reason="강점 일치"
            )
        ],
        metrics=[
            Metric(task_id="task_001", metric_name="온보딩 시간", baseline="2일", target="1일")
        ],
    )


def test_render_includes_intro_paragraph_first():
    blocks = render_roadmap_blocks(_goal(), _full_roadmap())
    assert blocks[0]["type"] == "paragraph"
    assert "팀 위키를 만들고" in blocks[0]["paragraph"]["rich_text"][0]["text"]["content"]


def test_render_includes_all_sections():
    blocks = render_roadmap_blocks(_goal(), _full_roadmap())
    heading_texts = [
        b["heading_2"]["rich_text"][0]["text"]["content"] for b in blocks if b["type"] == "heading_2"
    ]
    assert "이 업무들, AI로 풀어도 될까요?" in heading_texts
    assert "이번 로드맵" in heading_texts
    assert "역할 재분배 제안" in heading_texts
    assert "어떻게 확인해볼까요?" in heading_texts


def test_render_task_becomes_todo_block():
    blocks = render_roadmap_blocks(_goal(), _full_roadmap())
    todo_blocks = [b for b in blocks if b["type"] == "to_do"]
    assert len(todo_blocks) == 1
    assert "온보딩 문서 정리" in todo_blocks[0]["to_do"]["rich_text"][0]["text"]["content"]


def test_render_role_reassignment_includes_fixed_disclaimer():
    blocks = render_roadmap_blocks(_goal(), _full_roadmap())
    callouts = [b for b in blocks if b["type"] == "callout"]
    disclaimer_callout = [
        c for c in callouts if "실제 배분은 팀장님이 판단해주세요" in c["callout"]["rich_text"][0]["text"]["content"]
    ]
    assert len(disclaimer_callout) == 1


def test_render_adds_warning_callout_when_research_status_not_ok():
    roadmap = _full_roadmap().model_copy(update={"research_status": ResearchStatus.PARTIAL})
    blocks = render_roadmap_blocks(_goal(), roadmap)
    warning_callouts = [
        b for b in blocks if b["type"] == "callout" and b["callout"]["icon"]["emoji"] == "⚠️"
    ]
    assert len(warning_callouts) == 1
