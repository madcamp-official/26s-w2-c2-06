import json
from pathlib import Path

from fastapi.testclient import TestClient

import app.routers.roadmap as roadmap_router_module
from app.contracts.research import ResearchStatus
from app.contracts.roadmap import RoadmapResult
from app.main import app

FIXTURES_DIR = Path(__file__).parent.parent / "app" / "fixtures"


def _load(name: str) -> dict:
    return json.loads((FIXTURES_DIR / name).read_text())


def test_generate_endpoint_calls_generate_roadmap_and_returns_result(monkeypatch):
    captured = {}

    def fake_generate_roadmap(goal, research, onboarding, assets=None):
        captured["goal_id"] = goal.goal_id
        return RoadmapResult(goal_id=goal.goal_id, research_status=ResearchStatus.OK)

    monkeypatch.setattr(roadmap_router_module, "generate_roadmap", fake_generate_roadmap)

    client = TestClient(app)
    payload = {
        "goal": _load("goal_001.json"),
        "research": _load("research_context_goal_001.json"),
        "onboarding": _load("onboarding_001.json"),
    }

    response = client.post("/roadmap/generate", json=payload)

    assert response.status_code == 200
    assert response.json()["goal_id"] == "goal_001"
    assert captured["goal_id"] == "goal_001"


def test_publish_endpoint_returns_notion_url_and_page_id(monkeypatch):
    def fake_publish_roadmap(goal, roadmap, account_id, research=None, parent_page_id=None):
        return {"url": "https://notion.so/main", "page_id": "page-123"}

    monkeypatch.setattr(roadmap_router_module, "publish_roadmap", fake_publish_roadmap)

    client = TestClient(app)
    payload = {
        "goal": _load("goal_001.json"),
        "roadmap": RoadmapResult(goal_id="goal_001", research_status=ResearchStatus.OK).model_dump(
            mode="json"
        ),
    }

    response = client.post("/roadmap/publish", json=payload)

    assert response.status_code == 200
    assert response.json() == {"notion_url": "https://notion.so/main", "page_id": "page-123"}


def test_refresh_progress_endpoint_calls_refresh_progress(monkeypatch):
    captured = {}

    def fake_refresh_progress(page_id):
        captured["page_id"] = page_id
        return {"completed": 1, "total": 2, "completed_task_titles": ["task A"]}

    monkeypatch.setattr(roadmap_router_module, "refresh_progress", fake_refresh_progress)

    client = TestClient(app)
    response = client.post("/roadmap/page-123/refresh-progress")

    assert response.status_code == 200
    assert response.json() == {"completed": 1, "total": 2, "completed_task_titles": ["task A"]}
    assert captured["page_id"] == "page-123"
