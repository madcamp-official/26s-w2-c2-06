import app.notion.client as notion_client_module
from app.notion.client import create_page

_HEADERS = {"Authorization": "Bearer fake", "Notion-Version": "2026-03-11"}


class _FakeHttpResponse:
    def __init__(self, json_data: dict):
        self._json_data = json_data

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._json_data


def test_create_page_single_batch_only_posts_once(monkeypatch):
    calls = {"post": [], "patch": []}

    def fake_post(url, headers, json, timeout):
        calls["post"].append({"url": url, "json": json, "headers": headers})
        return _FakeHttpResponse({"id": "page123", "url": "https://notion.so/page123"})

    def fake_patch(url, headers, json, timeout):
        calls["patch"].append({"url": url, "json": json})
        return _FakeHttpResponse({})

    monkeypatch.setattr(notion_client_module.httpx, "post", fake_post)
    monkeypatch.setattr(notion_client_module.httpx, "patch", fake_patch)

    blocks = [{"type": "paragraph", "paragraph": {"rich_text": []}} for _ in range(10)]
    url = create_page("parent-id", "제목", blocks, _HEADERS)

    assert url == "https://notion.so/page123"
    assert len(calls["post"]) == 1
    assert calls["post"][0]["headers"] == _HEADERS
    assert len(calls["post"][0]["json"]["children"]) == 10
    assert calls["patch"] == []


def test_create_page_chunks_blocks_over_100(monkeypatch):
    calls = {"post": [], "patch": []}

    def fake_post(url, headers, json, timeout):
        calls["post"].append(json)
        return _FakeHttpResponse({"id": "page123", "url": "https://notion.so/page123"})

    def fake_patch(url, headers, json, timeout):
        calls["patch"].append(json)
        return _FakeHttpResponse({})

    monkeypatch.setattr(notion_client_module.httpx, "post", fake_post)
    monkeypatch.setattr(notion_client_module.httpx, "patch", fake_patch)

    blocks = [{"type": "paragraph", "paragraph": {"rich_text": []}} for _ in range(150)]
    create_page("parent-id", "제목", blocks, _HEADERS)

    assert len(calls["post"][0]["children"]) == 100
    assert len(calls["patch"]) == 1
    assert len(calls["patch"][0]["children"]) == 50
