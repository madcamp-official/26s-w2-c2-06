from fastapi.testclient import TestClient

import app.routers.notion_auth as notion_auth_router_module
from app.main import app

client = TestClient(app, follow_redirects=False)


def test_status_reports_not_connected_when_no_connection(monkeypatch):
    class _FakeSession:
        def close(self) -> None:
            return None

    monkeypatch.setattr(notion_auth_router_module, "get_session", lambda: _FakeSession())
    monkeypatch.setattr(notion_auth_router_module, "get_connection", lambda session, account_id: None)

    response = client.get("/notion/status", params={"account_id": "acc-1"})

    assert response.status_code == 200
    assert response.json() == {"connected": False, "workspace_name": None}


def test_status_reports_connected_with_workspace_name(monkeypatch):
    class _FakeConnection:
        workspace_name = "테스트 워크스페이스"

    class _FakeSession:
        def close(self) -> None:
            return None

    monkeypatch.setattr(notion_auth_router_module, "get_session", lambda: _FakeSession())
    monkeypatch.setattr(
        notion_auth_router_module, "get_connection", lambda session, account_id: _FakeConnection()
    )

    response = client.get("/notion/status", params={"account_id": "acc-1"})

    assert response.status_code == 200
    assert response.json() == {"connected": True, "workspace_name": "테스트 워크스페이스"}


def test_disconnect_removes_connection_and_reports_true(monkeypatch):
    class _FakeSession:
        def close(self) -> None:
            return None

    monkeypatch.setattr(notion_auth_router_module, "get_session", lambda: _FakeSession())
    monkeypatch.setattr(
        notion_auth_router_module, "delete_connection", lambda session, account_id: True
    )

    response = client.delete("/notion/connection", params={"account_id": "acc-1"})

    assert response.status_code == 200
    assert response.json() == {"disconnected": True}


def test_disconnect_reports_false_when_nothing_to_delete(monkeypatch):
    class _FakeSession:
        def close(self) -> None:
            return None

    monkeypatch.setattr(notion_auth_router_module, "get_session", lambda: _FakeSession())
    monkeypatch.setattr(
        notion_auth_router_module, "delete_connection", lambda session, account_id: False
    )

    response = client.delete("/notion/connection", params={"account_id": "acc-1"})

    assert response.status_code == 200
    assert response.json() == {"disconnected": False}


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
    monkeypatch.setattr(
        notion_auth_router_module, "list_shared_pages", lambda token: [{"id": "page-1", "title": "홈"}]
    )

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
    assert saved["default_page_id"] == "page-1"


def test_callback_shows_page_picker_when_multiple_pages_shared(monkeypatch):
    """페이지가 여러 개 공유돼 있으면 자동으로 첫 번째를 고르지 않고 선택 화면을 보여준다 —
    자동 선택 때문에 발행 대상이 재연결마다 바뀌는 사고가 실 운영에서 있었다(2026-07-15)."""
    monkeypatch.setattr(
        notion_auth_router_module,
        "exchange_code_for_token",
        lambda code: {
            "access_token": "tok",
            "workspace_id": "ws-1",
            "workspace_name": "테스트 워크스페이스",
            "bot_id": "bot-1",
        },
    )
    monkeypatch.setattr(
        notion_auth_router_module,
        "list_shared_pages",
        lambda token: [{"id": "page-1", "title": "노션 API 테스트용"}, {"id": "page-2", "title": "임시 페이지"}],
    )

    class _FakeConnection:
        workspace_name = "테스트 워크스페이스"
        default_page_id = "page-1"

    class _FakeSession:
        def close(self) -> None:
            return None

    monkeypatch.setattr(
        notion_auth_router_module, "save_connection", lambda session, **kwargs: _FakeConnection()
    )
    monkeypatch.setattr(notion_auth_router_module, "get_session", lambda: _FakeSession())

    response = client.get("/notion/callback", params={"code": "some-code", "state": "acc-1"})

    assert response.status_code == 200
    assert "어느 페이지에 발행할까요" in response.text
    assert "노션 API 테스트용" in response.text
    assert "임시 페이지" in response.text
    assert "/notion/select-page?account_id=acc-1&page_id=page-1" in response.text
    assert "/notion/select-page?account_id=acc-1&page_id=page-2" in response.text


def test_select_page_updates_connection_default_page(monkeypatch):
    class _FakeConnection:
        workspace_name = "테스트 워크스페이스"

    class _FakeSession:
        def close(self) -> None:
            return None

    captured = {}

    def fake_set_default_page(session, account_id, page_id):
        captured["account_id"] = account_id
        captured["page_id"] = page_id
        return _FakeConnection()

    monkeypatch.setattr(notion_auth_router_module, "get_session", lambda: _FakeSession())
    monkeypatch.setattr(notion_auth_router_module, "set_default_page", fake_set_default_page)

    response = client.get("/notion/select-page", params={"account_id": "acc-1", "page_id": "page-2"})

    assert response.status_code == 200
    assert "정했어요" in response.text
    assert captured == {"account_id": "acc-1", "page_id": "page-2"}


def test_select_page_shows_error_when_connection_missing(monkeypatch):
    class _FakeSession:
        def close(self) -> None:
            return None

    monkeypatch.setattr(notion_auth_router_module, "get_session", lambda: _FakeSession())
    monkeypatch.setattr(
        notion_auth_router_module, "set_default_page", lambda session, account_id, page_id: None
    )

    response = client.get("/notion/select-page", params={"account_id": "acc-1", "page_id": "page-2"})

    assert response.status_code == 200
    assert "찾을 수 없어요" in response.text


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
    monkeypatch.setattr(notion_auth_router_module, "list_shared_pages", lambda token: [])

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
