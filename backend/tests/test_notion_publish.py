import pytest

import app.notion.publish as publish_module
from app.contracts.goal import GoalDefinition, OrgConstraints
from app.contracts.onboarding import OnboardingData
from app.contracts.research import ResearchStatus
from app.contracts.roadmap import RoadmapResult
from app.notion.tracking_repository import WorkspaceRecord


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


def _onboarding() -> OnboardingData:
    return OnboardingData(team_size=3)


def _roadmap() -> RoadmapResult:
    return RoadmapResult(goal_id="goal_001", research_status=ResearchStatus.OK)


def _workspace() -> WorkspaceRecord:
    return WorkspaceRecord(
        account_id="acc-1",
        team_database_id="team-db",
        team_data_source_id="team-ds",
        opportunity_database_id="opp-db",
        opportunity_data_source_id="opp-ds",
        roadmap_database_id="roadmap-db",
        roadmap_data_source_id="roadmap-ds",
        dashboard_page_id="dash-page-id",
        dashboard_url="https://notion.so/dash-page-id",
        discovered_count_block_id="discovered-block",
        applied_count_block_id="applied-block",
    )


def _patch_connection(monkeypatch, access_token="tok", default_page_id="default-page"):
    monkeypatch.setattr(publish_module, "get_session", lambda: _FakeSession())
    monkeypatch.setattr(
        publish_module,
        "get_connection",
        lambda session, account_id: _FakeConnection(access_token, default_page_id),
    )


def test_publish_roadmap_uses_default_page_and_returns_dashboard_url(monkeypatch):
    _patch_connection(monkeypatch)
    captured = {}

    def fake_sync_roadmap(goal, roadmap, onboarding, account_id, parent_page_id, session, headers, research=None):
        captured["parent_page_id"] = parent_page_id
        captured["account_id"] = account_id
        captured["headers"] = headers
        return _workspace()

    monkeypatch.setattr(publish_module, "sync_roadmap", fake_sync_roadmap)
    monkeypatch.setattr(publish_module, "refresh_dashboard_stats", lambda account_id: None)

    result = publish_module.publish_roadmap(_goal(), _roadmap(), _onboarding(), account_id="acc-1")

    assert result == {"url": "https://notion.so/dash-page-id", "page_id": "dash-page-id"}
    assert captured["parent_page_id"] == "default-page"
    assert captured["account_id"] == "acc-1"
    assert captured["headers"]["Authorization"] == "Bearer tok"


def test_publish_roadmap_prefers_explicit_parent_page_id(monkeypatch):
    _patch_connection(monkeypatch)
    captured = {}

    def fake_sync_roadmap(goal, roadmap, onboarding, account_id, parent_page_id, session, headers, research=None):
        captured["parent_page_id"] = parent_page_id
        return _workspace()

    monkeypatch.setattr(publish_module, "sync_roadmap", fake_sync_roadmap)
    monkeypatch.setattr(publish_module, "refresh_dashboard_stats", lambda account_id: None)

    publish_module.publish_roadmap(
        _goal(), _roadmap(), _onboarding(), account_id="acc-1", parent_page_id="explicit-page"
    )

    assert captured["parent_page_id"] == "explicit-page"


def test_publish_roadmap_refreshes_dashboard_stats_after_sync(monkeypatch):
    _patch_connection(monkeypatch)
    monkeypatch.setattr(publish_module, "sync_roadmap", lambda *a, **k: _workspace())

    refreshed = {}
    monkeypatch.setattr(
        publish_module, "refresh_dashboard_stats", lambda account_id: refreshed.setdefault("account_id", account_id)
    )

    publish_module.publish_roadmap(_goal(), _roadmap(), _onboarding(), account_id="acc-1")

    assert refreshed["account_id"] == "acc-1"


def test_publish_roadmap_raises_when_account_not_connected(monkeypatch):
    monkeypatch.setattr(publish_module, "get_session", lambda: _FakeSession())
    monkeypatch.setattr(publish_module, "get_connection", lambda session, account_id: None)

    with pytest.raises(ValueError):
        publish_module.publish_roadmap(_goal(), _roadmap(), _onboarding(), account_id="acc-unknown")


def test_publish_roadmap_raises_when_no_page_available(monkeypatch):
    _patch_connection(monkeypatch, default_page_id=None)

    with pytest.raises(ValueError):
        publish_module.publish_roadmap(_goal(), _roadmap(), _onboarding(), account_id="acc-1")


def test_publish_report_raises_when_roadmap_missing():
    with pytest.raises(ValueError):
        publish_module.publish_report(_goal(), _onboarding(), account_id="acc-1", roadmap=None)


def test_publish_report_delegates_to_publish_roadmap(monkeypatch):
    captured = {}

    def fake_publish_roadmap(goal, roadmap, onboarding, account_id, parent_page_id=None, research=None):
        captured["args"] = (goal, roadmap, onboarding, account_id, parent_page_id)
        return {"url": "https://notion.so/dash-page-id", "page_id": "dash-page-id"}

    monkeypatch.setattr(publish_module, "publish_roadmap", fake_publish_roadmap)

    result = publish_module.publish_report(
        _goal(), _onboarding(), account_id="acc-1", roadmap=_roadmap()
    )

    assert result == {"url": "https://notion.so/dash-page-id", "page_id": "dash-page-id"}
    assert captured["args"][3] == "acc-1"
