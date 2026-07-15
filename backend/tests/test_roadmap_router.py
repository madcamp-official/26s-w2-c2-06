import json
from pathlib import Path

from fastapi.testclient import TestClient

import app.routers.roadmap as roadmap_router_module
from app.contracts.research import ResearchContext, ResearchStatus
from app.contracts.roadmap import RoadmapResult
from app.main import app

FIXTURES_DIR = Path(__file__).parent.parent / "app" / "fixtures"


def _load(name: str) -> dict:
    return json.loads((FIXTURES_DIR / name).read_text())


def test_generate_endpoint_calls_run_research_and_generate_roadmap(monkeypatch):
    captured = {}
    fake_research = ResearchContext(
        goal_id="goal_001", retrieved_at="2026-07-13T00:00:00Z", status=ResearchStatus.OK, findings=[]
    )

    def fake_run_research(goal):
        captured["research_goal_id"] = goal.goal_id
        return fake_research

    def fake_generate_roadmap(goal, research, onboarding, assets=None):
        captured["goal_id"] = goal.goal_id
        captured["research"] = research
        return RoadmapResult(goal_id=goal.goal_id, research_status=ResearchStatus.OK)

    monkeypatch.setattr(roadmap_router_module, "run_research", fake_run_research)
    monkeypatch.setattr(roadmap_router_module, "generate_roadmap", fake_generate_roadmap)

    client = TestClient(app)
    payload = {
        "goal": _load("goal_001.json"),
        "onboarding": _load("onboarding_001.json"),
    }

    response = client.post("/roadmap/generate", json=payload)

    assert response.status_code == 200
    assert response.json()["goal_id"] == "goal_001"
    assert captured["goal_id"] == "goal_001"
    assert captured["research_goal_id"] == "goal_001"
    assert captured["research"] is fake_research


def test_publish_endpoint_calls_publish_roadmap_and_returns_notion_url_and_page_id(monkeypatch):
    captured = {}
    fake_research = ResearchContext(
        goal_id="goal_001", retrieved_at="2026-07-13T00:00:00Z", status=ResearchStatus.OK, findings=[]
    )

    def fake_publish_roadmap(goal, roadmap, onboarding, account_id, parent_page_id=None, research=None):
        captured["goal_id"] = goal.goal_id
        captured["onboarding_team_size"] = onboarding.team_size
        captured["account_id"] = account_id
        captured["research"] = research
        return {"url": "https://notion.so/main", "page_id": "page-123"}

    monkeypatch.setattr(roadmap_router_module, "run_research", lambda goal: fake_research)
    monkeypatch.setattr(roadmap_router_module, "publish_roadmap", fake_publish_roadmap)

    client = TestClient(app)
    payload = {
        "goal": _load("goal_001.json"),
        "roadmap": RoadmapResult(goal_id="goal_001", research_status=ResearchStatus.OK).model_dump(
            mode="json"
        ),
        "onboarding": _load("onboarding_001.json"),
    }

    response = client.post("/roadmap/publish", json=payload)

    assert response.status_code == 200
    assert response.json() == {"notion_url": "https://notion.so/main", "page_id": "page-123"}
    assert captured["goal_id"] == "goal_001"
    assert captured["onboarding_team_size"] == _load("onboarding_001.json")["team_size"]
    assert captured["research"] is fake_research


def test_publish_endpoint_returns_400_with_message_when_account_not_connected(monkeypatch):
    def fake_publish_roadmap(goal, roadmap, onboarding, account_id, parent_page_id=None, research=None):
        raise ValueError(f"계정 '{account_id}'이 Notion과 연결되어 있지 않습니다.")

    monkeypatch.setattr(roadmap_router_module, "run_research", lambda goal: None)
    monkeypatch.setattr(roadmap_router_module, "publish_roadmap", fake_publish_roadmap)

    client = TestClient(app)
    payload = {
        "goal": _load("goal_001.json"),
        "roadmap": RoadmapResult(goal_id="goal_001", research_status=ResearchStatus.OK).model_dump(
            mode="json"
        ),
        "onboarding": _load("onboarding_001.json"),
    }

    response = client.post("/roadmap/publish", json=payload)

    assert response.status_code == 400
    assert "연결되어 있지 않습니다" in response.json()["detail"]


def test_generate_and_publish_endpoint_calls_run_research_once_and_returns_notion_url(monkeypatch):
    captured = {"run_research_calls": 0}
    fake_research = ResearchContext(
        goal_id="goal_001", retrieved_at="2026-07-13T00:00:00Z", status=ResearchStatus.OK, findings=[]
    )

    def fake_run_research(goal):
        captured["run_research_calls"] += 1
        return fake_research

    def fake_generate_roadmap(goal, research, onboarding, assets=None):
        captured["generate_research"] = research
        return RoadmapResult(goal_id=goal.goal_id, research_status=ResearchStatus.OK)

    def fake_publish_roadmap(goal, roadmap, onboarding, account_id, parent_page_id=None, research=None):
        captured["publish_called"] = True
        return {"url": "https://notion.so/main", "page_id": "page-123"}

    monkeypatch.setattr(roadmap_router_module, "run_research", fake_run_research)
    monkeypatch.setattr(roadmap_router_module, "generate_roadmap", fake_generate_roadmap)
    monkeypatch.setattr(roadmap_router_module, "publish_roadmap", fake_publish_roadmap)

    client = TestClient(app)
    payload = {
        "goal": _load("goal_001.json"),
        "onboarding": _load("onboarding_001.json"),
    }

    response = client.post("/roadmap/generate-and-publish", json=payload)

    assert response.status_code == 200
    assert response.json() == {"notion_url": "https://notion.so/main", "page_id": "page-123"}
    assert captured["run_research_calls"] == 1
    assert captured["generate_research"] is fake_research
    assert captured["publish_called"] is True
