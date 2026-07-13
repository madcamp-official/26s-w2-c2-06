import pytest

import app.notion.publish as publish_module
from app.contracts.goal import GoalDefinition, OrgConstraints
from app.contracts.research import ResearchStatus
from app.contracts.roadmap import RoadmapResult


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


def _roadmap() -> RoadmapResult:
    return RoadmapResult(goal_id="goal_001", research_status=ResearchStatus.OK)


def test_publish_roadmap_uses_connection_default_page_when_not_overridden(monkeypatch):
    captured = {}
    monkeypatch.setattr(publish_module, "get_session", lambda: _FakeSession())
    monkeypatch.setattr(
        publish_module, "get_connection", lambda session, account_id: _FakeConnection("tok", "default-page")
    )

    def fake_create_page(parent_page_id, title, blocks, headers):
        captured["parent_page_id"] = parent_page_id
        captured["headers"] = headers
        return "https://notion.so/fake"

    monkeypatch.setattr(publish_module, "create_page", fake_create_page)

    url = publish_module.publish_roadmap(_goal(), _roadmap(), account_id="acc-1")

    assert url == "https://notion.so/fake"
    assert captured["parent_page_id"] == "default-page"
    assert captured["headers"]["Authorization"] == "Bearer tok"


def test_publish_roadmap_prefers_explicit_parent_page_id(monkeypatch):
    captured = {}
    monkeypatch.setattr(publish_module, "get_session", lambda: _FakeSession())
    monkeypatch.setattr(
        publish_module, "get_connection", lambda session, account_id: _FakeConnection("tok", "default-page")
    )
    monkeypatch.setattr(
        publish_module,
        "create_page",
        lambda parent_page_id, title, blocks, headers: captured.setdefault(
            "parent_page_id", parent_page_id
        )
        or "url",
    )

    publish_module.publish_roadmap(_goal(), _roadmap(), account_id="acc-1", parent_page_id="explicit-page")

    assert captured["parent_page_id"] == "explicit-page"


def test_publish_roadmap_raises_when_account_not_connected(monkeypatch):
    monkeypatch.setattr(publish_module, "get_session", lambda: _FakeSession())
    monkeypatch.setattr(publish_module, "get_connection", lambda session, account_id: None)

    with pytest.raises(ValueError):
        publish_module.publish_roadmap(_goal(), _roadmap(), account_id="acc-unknown")


def test_publish_roadmap_raises_when_no_page_available(monkeypatch):
    monkeypatch.setattr(publish_module, "get_session", lambda: _FakeSession())
    monkeypatch.setattr(
        publish_module, "get_connection", lambda session, account_id: _FakeConnection("tok", None)
    )

    with pytest.raises(ValueError):
        publish_module.publish_roadmap(_goal(), _roadmap(), account_id="acc-1")
