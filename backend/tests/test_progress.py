import pytest

import app.notion.progress as progress_module
from app.notion.tracking_repository import PublishedRoadmapRecord, TrackedTask


class _FakeSession:
    def close(self) -> None:
        return None


class _FakeConnection:
    def __init__(self, access_token: str = "tok"):
        self.access_token = access_token


def _record(tasks: list[TrackedTask], stats_block_id: str | None = "stats-1") -> PublishedRoadmapRecord:
    return PublishedRoadmapRecord(
        page_id="page-1", account_id="acc-1", stats_block_id=stats_block_id, tasks=tasks
    )


def test_refresh_progress_counts_checked_tasks_and_updates_summary(monkeypatch):
    tasks = [
        TrackedTask("task_001", "온보딩 정리", "block-1"),
        TrackedTask("task_002", "보고서 자동화", "block-2"),
    ]
    monkeypatch.setattr(progress_module, "get_session", lambda: _FakeSession())
    monkeypatch.setattr(
        progress_module, "get_published_roadmap", lambda session, page_id: _record(tasks)
    )
    monkeypatch.setattr(progress_module, "get_connection", lambda session, account_id: _FakeConnection())

    block_states = {"block-1": True, "block-2": False}
    monkeypatch.setattr(
        progress_module,
        "get_block",
        lambda block_id, headers: {"to_do": {"checked": block_states[block_id]}},
    )

    captured = {}

    def fake_update_callout_text(block_id, content, headers):
        captured["block_id"] = block_id
        captured["content"] = content

    monkeypatch.setattr(progress_module, "update_callout_text", fake_update_callout_text)

    result = progress_module.refresh_progress("page-1")

    assert result == {"completed": 1, "total": 2, "completed_task_titles": ["온보딩 정리"]}
    assert captured["block_id"] == "stats-1"
    assert "완료 1/2" in captured["content"]


def test_refresh_progress_skips_summary_update_when_no_stats_block(monkeypatch):
    tasks = [TrackedTask("task_001", "t", "block-1")]
    monkeypatch.setattr(progress_module, "get_session", lambda: _FakeSession())
    monkeypatch.setattr(
        progress_module,
        "get_published_roadmap",
        lambda session, page_id: _record(tasks, stats_block_id=None),
    )
    monkeypatch.setattr(progress_module, "get_connection", lambda session, account_id: _FakeConnection())
    monkeypatch.setattr(progress_module, "get_block", lambda block_id, headers: {"to_do": {"checked": True}})

    def fail_if_called(*args, **kwargs):
        raise AssertionError("stats_block_id가 없으면 update_callout_text를 호출하면 안 됨")

    monkeypatch.setattr(progress_module, "update_callout_text", fail_if_called)

    result = progress_module.refresh_progress("page-1")
    assert result["completed"] == 1


def test_refresh_progress_raises_when_page_not_found(monkeypatch):
    monkeypatch.setattr(progress_module, "get_session", lambda: _FakeSession())
    monkeypatch.setattr(progress_module, "get_published_roadmap", lambda session, page_id: None)

    with pytest.raises(ValueError):
        progress_module.refresh_progress("no-such-page")


def test_refresh_progress_raises_when_connection_missing(monkeypatch):
    monkeypatch.setattr(progress_module, "get_session", lambda: _FakeSession())
    monkeypatch.setattr(
        progress_module, "get_published_roadmap", lambda session, page_id: _record([])
    )
    monkeypatch.setattr(progress_module, "get_connection", lambda session, account_id: None)

    with pytest.raises(ValueError):
        progress_module.refresh_progress("page-1")
