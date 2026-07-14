import app.notion.client as notion_client_module
from app.notion.client import (
    create_database,
    create_database_row,
    create_page,
    query_data_source,
    update_page_properties,
)

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
    page = create_page("parent-id", "제목", blocks, _HEADERS)

    assert page == {"id": "page123", "url": "https://notion.so/page123"}
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


def test_create_database_returns_database_and_data_source_ids(monkeypatch):
    captured = {}

    def fake_post(url, headers, json, timeout):
        captured["url"] = url
        captured["json"] = json
        return _FakeHttpResponse(
            {"id": "db-1", "data_sources": [{"id": "ds-1", "name": "팀원"}]}
        )

    monkeypatch.setattr(notion_client_module.httpx, "post", fake_post)

    result = create_database("parent-page", "팀원", {"팀원": {"title": {}}}, _HEADERS)

    assert result == {"database_id": "db-1", "data_source_id": "ds-1"}
    assert captured["url"].endswith("/databases")
    assert captured["json"]["parent"] == {"type": "page_id", "page_id": "parent-page"}
    assert captured["json"]["initial_data_source"]["properties"] == {"팀원": {"title": {}}}


def test_create_database_falls_back_to_database_id_when_no_data_sources(monkeypatch):
    monkeypatch.setattr(
        notion_client_module.httpx, "post", lambda url, headers, json, timeout: _FakeHttpResponse({"id": "db-1"})
    )

    result = create_database("parent-page", "팀원", {}, _HEADERS)

    assert result == {"database_id": "db-1", "data_source_id": "db-1"}


def test_create_database_row_posts_to_data_source_parent(monkeypatch):
    captured = {}

    def fake_post(url, headers, json, timeout):
        captured["json"] = json
        return _FakeHttpResponse({"id": "row-1", "url": "https://notion.so/row-1"})

    monkeypatch.setattr(notion_client_module.httpx, "post", fake_post)

    page = create_database_row("ds-1", {"Task": {"title": []}}, _HEADERS)

    assert page == {"id": "row-1", "url": "https://notion.so/row-1"}
    assert captured["json"]["parent"] == {"type": "data_source_id", "data_source_id": "ds-1"}
    assert captured["json"]["properties"] == {"Task": {"title": []}}


def test_update_page_properties_patches_page(monkeypatch):
    captured = {}

    def fake_patch(url, headers, json, timeout):
        captured["url"] = url
        captured["json"] = json
        return _FakeHttpResponse({})

    monkeypatch.setattr(notion_client_module.httpx, "patch", fake_patch)

    update_page_properties("page-1", {"현재값": {"number": 30}}, _HEADERS)

    assert captured["url"].endswith("/pages/page-1")
    assert captured["json"] == {"properties": {"현재값": {"number": 30}}}


def test_query_data_source_returns_results(monkeypatch):
    captured = {}

    def fake_post(url, headers, json, timeout):
        captured["url"] = url
        return _FakeHttpResponse({"results": [{"id": "row-1"}, {"id": "row-2"}]})

    monkeypatch.setattr(notion_client_module.httpx, "post", fake_post)

    rows = query_data_source("ds-1", _HEADERS)

    assert rows == [{"id": "row-1"}, {"id": "row-2"}]
    assert captured["url"].endswith("/data_sources/ds-1/query")
