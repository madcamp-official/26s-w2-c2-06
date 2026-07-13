from fastapi.testclient import TestClient

import app.routers.notion_auth as notion_auth_router_module
from app.main import app

client = TestClient(app, follow_redirects=False)


def test_connect_redirects_to_notion_authorize_url(monkeypatch):
    monkeypatch.setattr(
        notion_auth_router_module,
        "build_authorize_url",
        lambda state: f"https://api.notion.com/v1/oauth/authorize?state={state}",
    )

    response = client.get("/notion/connect", params={"account_id": "acc-1"})

    assert response.status_code in (302, 307)
    assert "state=acc-1" in response.headers["location"]


def test_callback_exchanges_code_and_saves_connection(monkeypatch):
    monkeypatch.setattr(
        notion_auth_router_module,
        "exchange_code_for_token",
        lambda code: {
            "access_token": "tok",
            "workspace_id": "ws-1",
            "workspace_name": "테스트 워크스페이스",
            "bot_id": "bot-1",
            "refresh_token": None,
        },
    )
    monkeypatch.setattr(notion_auth_router_module, "find_default_page_id", lambda token: "page-1")

    saved = {}

    class _FakeConnection:
        workspace_name = "테스트 워크스페이스"
        default_page_id = "page-1"

    def fake_save_connection(session, **kwargs):
        saved.update(kwargs)
        return _FakeConnection()

    class _FakeSession:
        def close(self) -> None:
            return None

    monkeypatch.setattr(notion_auth_router_module, "save_connection", fake_save_connection)
    monkeypatch.setattr(notion_auth_router_module, "get_session", lambda: _FakeSession())

    response = client.get("/notion/callback", params={"code": "some-code", "state": "acc-1"})

    assert response.status_code == 200
    assert "테스트 워크스페이스" in response.text
    assert "연결 완료" in response.text
    assert saved["account_id"] == "acc-1"
    assert saved["access_token"] == "tok"


def test_callback_shows_friendly_message_when_user_denies_access():
    response = client.get("/notion/callback", params={"state": "acc-1", "error": "access_denied"})

    assert response.status_code == 200
    assert "완료되지 않았어요" in response.text


def test_callback_shows_message_when_no_page_shared(monkeypatch):
    monkeypatch.setattr(
        notion_auth_router_module,
        "exchange_code_for_token",
        lambda code: {
            "access_token": "tok",
            "workspace_id": "ws-1",
            "workspace_name": "빈 워크스페이스",
            "bot_id": "bot-1",
        },
    )
    monkeypatch.setattr(notion_auth_router_module, "find_default_page_id", lambda token: None)

    class _FakeConnection:
        workspace_name = "빈 워크스페이스"
        default_page_id = None

    class _FakeSession:
        def close(self) -> None:
            return None

    monkeypatch.setattr(
        notion_auth_router_module, "save_connection", lambda session, **kwargs: _FakeConnection()
    )
    monkeypatch.setattr(notion_auth_router_module, "get_session", lambda: _FakeSession())

    response = client.get("/notion/callback", params={"code": "some-code", "state": "acc-1"})

    assert response.status_code == 200
    assert "공유된 페이지가 없어요" in response.text
