import app.notion.oauth as oauth_module
from app.core.config import settings
from app.notion.oauth import build_authorize_url, exchange_code_for_token, list_shared_pages


class _FakeHttpResponse:
    def __init__(self, json_data: dict):
        self._json_data = json_data

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._json_data


def test_build_authorize_url_includes_state_and_client_id(monkeypatch):
    monkeypatch.setattr(settings, "notion_oauth_client_id", "client-abc")
    monkeypatch.setattr(settings, "notion_oauth_redirect_uri", "http://localhost:8000/notion/callback")

    url = build_authorize_url(state="account-1")

    assert "client_id=client-abc" in url
    assert "state=account-1" in url
    assert "response_type=code" in url
    assert "owner=user" in url


def test_exchange_code_for_token_uses_basic_auth(monkeypatch):
    captured = {}

    def fake_post(url, auth, headers, json, timeout):
        captured["url"] = url
        captured["auth"] = auth
        captured["json"] = json
        return _FakeHttpResponse({"access_token": "tok", "workspace_id": "ws1", "bot_id": "bot1"})

    monkeypatch.setattr(oauth_module.httpx, "post", fake_post)
    monkeypatch.setattr(settings, "notion_oauth_client_id", "client-abc")
    monkeypatch.setattr(settings, "notion_oauth_client_secret", "secret-xyz")

    result = exchange_code_for_token("some-code")

    assert result["access_token"] == "tok"
    assert captured["auth"] == ("client-abc", "secret-xyz")
    assert captured["json"]["code"] == "some-code"
    assert captured["json"]["grant_type"] == "authorization_code"


def test_list_shared_pages_returns_id_and_title_for_each_result(monkeypatch):
    def fake_post(url, headers, json, timeout):
        assert "search" in url
        return _FakeHttpResponse({
            "results": [
                {"id": "page-1", "properties": {"title": {"title": [{"plain_text": "노션 API 테스트용"}]}}},
                {"id": "page-2", "properties": {"title": {"title": [{"plain_text": "Template Example"}]}}},
            ]
        })

    monkeypatch.setattr(oauth_module.httpx, "post", fake_post)

    pages = list_shared_pages("some-token")

    assert pages == [
        {"id": "page-1", "title": "노션 API 테스트용"},
        {"id": "page-2", "title": "Template Example"},
    ]


def test_list_shared_pages_falls_back_to_placeholder_when_title_empty(monkeypatch):
    def fake_post(url, headers, json, timeout):
        return _FakeHttpResponse({"results": [{"id": "page-1", "properties": {"title": {"title": []}}}]})

    monkeypatch.setattr(oauth_module.httpx, "post", fake_post)

    assert list_shared_pages("some-token") == [{"id": "page-1", "title": "(제목 없음)"}]


def test_list_shared_pages_returns_empty_list_when_no_results(monkeypatch):
    def fake_post(url, headers, json, timeout):
        return _FakeHttpResponse({"results": []})

    monkeypatch.setattr(oauth_module.httpx, "post", fake_post)

    assert list_shared_pages("some-token") == []
