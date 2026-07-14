import pytest

import app.notion.progress as progress_module
from app.notion.tracking_repository import WorkspaceRecord


class _FakeSession:
    def close(self) -> None:
        return None


class _FakeConnection:
    def __init__(self, access_token: str = "tok"):
        self.access_token = access_token


def _workspace() -> WorkspaceRecord:
    return WorkspaceRecord(
        account_id="acc-1",
        team_database_id="team-db",
        team_data_source_id="team-ds",
        opportunity_database_id="opp-db",
        opportunity_data_source_id="opp-ds",
        roadmap_database_id="roadmap-db",
        roadmap_data_source_id="roadmap-ds",
        dashboard_page_id="dash-page",
        dashboard_url="https://notion.so/dash-page",
        discovered_count_block_id="discovered-block",
        applied_count_block_id="applied-block",
    )


def _work_item_row(fitness: str) -> dict:
    return {"properties": {"적합성": {"select": {"name": fitness} if fitness else None}}}


def _task_row(baseline: float | None, current: float | None) -> dict:
    return {"properties": {"기존값": {"number": baseline}, "현재값": {"number": current}}}


def _patch_common(monkeypatch, work_items, tasks):
    monkeypatch.setattr(progress_module, "get_session", lambda: _FakeSession())
    monkeypatch.setattr(progress_module, "get_workspace", lambda session, account_id: _workspace())
    monkeypatch.setattr(
        progress_module, "get_connection", lambda session, account_id: _FakeConnection()
    )

    def fake_query_data_source(data_source_id, headers):
        if data_source_id == "opp-ds":
            return work_items
        if data_source_id == "roadmap-ds":
            return tasks
        raise AssertionError(f"unexpected data_source_id: {data_source_id}")

    monkeypatch.setattr(progress_module, "query_data_source", fake_query_data_source)


def test_refresh_dashboard_stats_counts_discovered_and_applied(monkeypatch):
    work_items = [_work_item_row("적합"), _work_item_row("부분 적합"), _work_item_row("부적합")]
    tasks = [_task_row(180, 30), _task_row(60, 60), _task_row(None, None)]
    _patch_common(monkeypatch, work_items, tasks)

    captured = []
    monkeypatch.setattr(
        progress_module,
        "update_callout_text",
        lambda block_id, content, headers: captured.append((block_id, content)),
    )

    result = progress_module.refresh_dashboard_stats("acc-1")

    # 적합/부분 적합만 "발견"으로 세고 부적합은 제외
    assert result == {"discovered": 2, "total_work_items": 3, "applied": 1, "total_tasks": 3}
    assert captured[0][0] == "discovered-block"
    assert "발견한 AI Opportunity 수: 2건" in captured[0][1]
    assert captured[1][0] == "applied-block"
    assert "AX 적용한 업무 수: 1건" in captured[1][1]


def test_refresh_dashboard_stats_raises_when_workspace_missing(monkeypatch):
    monkeypatch.setattr(progress_module, "get_session", lambda: _FakeSession())
    monkeypatch.setattr(progress_module, "get_workspace", lambda session, account_id: None)

    with pytest.raises(ValueError):
        progress_module.refresh_dashboard_stats("no-such-account")


def test_refresh_dashboard_stats_raises_when_connection_missing(monkeypatch):
    monkeypatch.setattr(progress_module, "get_session", lambda: _FakeSession())
    monkeypatch.setattr(progress_module, "get_workspace", lambda session, account_id: _workspace())
    monkeypatch.setattr(progress_module, "get_connection", lambda session, account_id: None)

    with pytest.raises(ValueError):
        progress_module.refresh_dashboard_stats("acc-1")
