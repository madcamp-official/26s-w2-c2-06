import pytest

import app.notion.publish as publish_module
from app.contracts.goal import GoalDefinition, OrgConstraints
from app.contracts.research import ResearchStatus
from app.contracts.roadmap import Metric, RoadmapResult, Task
from app.notion.blocks import render_roadmap_page_blocks


class _FakeSession:
    def close(self) -> None:
        return None


class _FakeConnection:
    def __init__(self, access_token: str, default_page_id: str | None):
        self.access_token = access_token
        self.default_page_id = default_page_id


def _goal() -> GoalDefinition:
    return GoalDefinition(
        goal_id="goal_001", goal_text="목표", org_constraints=OrgConstraints(security_level="high")
    )


def _task(task_id="task_001") -> Task:
    return Task(
        task_id=task_id,
        title="t",
        layer=1,
        week=1,
        difficulty="쉬움",
        est_time="1시간",
        expected_effect="효과",
        failure_risk="위험",
    )


def _patch_connection(monkeypatch, access_token="tok", default_page_id="default-page"):
    monkeypatch.setattr(publish_module, "get_session", lambda: _FakeSession())
    monkeypatch.setattr(
        publish_module,
        "get_connection",
        lambda session, account_id: _FakeConnection(access_token, default_page_id),
    )


def test_publish_roadmap_without_tasks_returns_url_and_page_id_and_skips_tracking(monkeypatch):
    captured = {}
    _patch_connection(monkeypatch)

    def fake_create_page(parent_page_id, title, blocks, headers):
        captured["parent_page_id"] = parent_page_id
        captured["headers"] = headers
        return {"id": "main-page-id", "url": "https://notion.so/main"}

    def fail_if_called(*args, **kwargs):
        raise AssertionError("tasks가 없으면 get_block_children이 호출되면 안 됨")

    monkeypatch.setattr(publish_module, "create_page", fake_create_page)
    monkeypatch.setattr(publish_module, "get_block_children", fail_if_called)

    roadmap = RoadmapResult(goal_id="goal_001", research_status=ResearchStatus.OK, tasks=[])
    result = publish_module.publish_roadmap(_goal(), roadmap, account_id="acc-1")

    assert result == {"url": "https://notion.so/main", "page_id": "main-page-id"}
    assert captured["parent_page_id"] == "default-page"
    assert captured["headers"]["Authorization"] == "Bearer tok"


def test_publish_roadmap_prefers_explicit_parent_page_id(monkeypatch):
    captured = {}
    _patch_connection(monkeypatch)

    def fake_create_page(parent_page_id, title, blocks, headers):
        captured["parent_page_id"] = parent_page_id
        return {"id": "p", "url": "u"}

    monkeypatch.setattr(publish_module, "create_page", fake_create_page)

    roadmap = RoadmapResult(goal_id="goal_001", research_status=ResearchStatus.OK, tasks=[])
    publish_module.publish_roadmap(_goal(), roadmap, account_id="acc-1", parent_page_id="explicit-page")

    assert captured["parent_page_id"] == "explicit-page"


def test_publish_roadmap_raises_when_account_not_connected(monkeypatch):
    monkeypatch.setattr(publish_module, "get_session", lambda: _FakeSession())
    monkeypatch.setattr(publish_module, "get_connection", lambda session, account_id: None)

    roadmap = RoadmapResult(goal_id="goal_001", research_status=ResearchStatus.OK, tasks=[_task()])
    with pytest.raises(ValueError):
        publish_module.publish_roadmap(_goal(), roadmap, account_id="acc-unknown")


def test_publish_roadmap_raises_when_no_page_available(monkeypatch):
    _patch_connection(monkeypatch, default_page_id=None)

    roadmap = RoadmapResult(goal_id="goal_001", research_status=ResearchStatus.OK, tasks=[_task()])
    with pytest.raises(ValueError):
        publish_module.publish_roadmap(_goal(), roadmap, account_id="acc-1")


def test_publish_roadmap_tracks_checkbox_ids_for_column_and_plain_tasks(monkeypatch):
    _patch_connection(monkeypatch)

    monkeypatch.setattr(
        publish_module, "create_page", lambda *a, **k: {"id": "main-page-id", "url": "https://notion.so/main"}
    )

    # task_001은 지표가 있어서 column_list로, task_002는 지표가 없어서 순수 to_do로 렌더링됨
    roadmap = RoadmapResult(
        goal_id="goal_001",
        research_status=ResearchStatus.OK,
        tasks=[_task("task_001"), _task("task_002")],
        metrics=[Metric(task_id="task_001", metric_name="m", baseline="b", target="t")],
    )

    # 실제 레이아웃 계산 결과(어떤 top-level 인덱스가 stats/task_001/task_002인지)를 그대로 써서
    # top_children 목록을 만든다 — blocks.py 내부 순서를 이 테스트에서 다시 하드코딩하지 않기 위함.
    layout = render_roadmap_page_blocks(_goal(), roadmap)
    top_children = [{"id": f"placeholder-{i}"} for i in range(len(layout.blocks))]
    top_children[layout.stats_block_index] = {"id": "stats-block-id"}
    top_children[layout.task_positions["task_001"].top_level_index] = {"id": "col-list-id"}
    top_children[layout.task_positions["task_002"].top_level_index] = {"id": "plain-todo-id"}

    nested = {
        "col-list-id": [{"id": "col-left-id"}, {"id": "col-right-id"}],
        "col-left-id": [{"id": "checkbox-task-001-id"}],
    }

    def fake_get_block_children(block_id, headers):
        if block_id == "main-page-id":
            return top_children
        return nested[block_id]

    monkeypatch.setattr(publish_module, "get_block_children", fake_get_block_children)

    saved = {}

    def fake_save_published_roadmap(session, page_id, account_id, stats_block_id, tasks):
        saved["page_id"] = page_id
        saved["account_id"] = account_id
        saved["stats_block_id"] = stats_block_id
        saved["tasks"] = {t.task_id: t.checkbox_block_id for t in tasks}

    monkeypatch.setattr(publish_module, "save_published_roadmap", fake_save_published_roadmap)

    result = publish_module.publish_roadmap(_goal(), roadmap, account_id="acc-1")

    assert result["page_id"] == "main-page-id"
    assert saved["page_id"] == "main-page-id"
    assert saved["account_id"] == "acc-1"
    assert saved["stats_block_id"] == "stats-block-id"
    assert saved["tasks"]["task_001"] == "checkbox-task-001-id"
    assert saved["tasks"]["task_002"] == "plain-todo-id"
