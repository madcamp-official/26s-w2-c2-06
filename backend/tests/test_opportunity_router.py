from fastapi.testclient import TestClient

from app.main import app
from app.schemas.bp_matching import DUMMY_MATCH_RESULT
from app.schemas.task_judgment import DUMMY_JUDGMENT

client = TestClient(app)


def test_format_endpoint_returns_opportunity_card():
    payload = {
        "match_result": DUMMY_MATCH_RESULT.model_dump(mode="json"),
        "judgment": DUMMY_JUDGMENT.model_dump(mode="json"),
    }

    response = client.post("/opportunities/format", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["task_name"] == DUMMY_JUDGMENT.task_name
    assert body["metrics"]["time_saved_minutes_estimate"] == 45
    assert body["metrics"]["is_ai_assistable"] is True
    assert len(body["matched_cases"]) == len(DUMMY_MATCH_RESULT.matched_cases)
