"""Notion REST 호출 (공식 SDK 미사용). 인증은 호출하는 쪽에서 headers로 넘긴다 —
계정마다 다른 access_token을 쓰므로 이 모듈은 특정 계정을 알지 못한다 (app/notion/publish.py 참고)."""

import httpx

_API_BASE = "https://api.notion.com/v1"
_MAX_BLOCKS_PER_REQUEST = 100


def create_page(parent_page_id: str, title: str, blocks: list[dict], headers: dict[str, str]) -> dict:
    """blocks[:100]으로 페이지를 만들고, 나머지는 이어붙인다. {"id", "url"}을 반환한다."""
    first_batch, remaining = blocks[:_MAX_BLOCKS_PER_REQUEST], blocks[_MAX_BLOCKS_PER_REQUEST:]

    body = {
        "parent": {"type": "page_id", "page_id": parent_page_id},
        "properties": {"title": {"title": [{"type": "text", "text": {"content": title}}]}},
        "children": first_batch,
    }
    response = httpx.post(f"{_API_BASE}/pages", headers=headers, json=body, timeout=30)
    response.raise_for_status()
    page = response.json()

    for i in range(0, len(remaining), _MAX_BLOCKS_PER_REQUEST):
        _append_children(page["id"], remaining[i : i + _MAX_BLOCKS_PER_REQUEST], headers)

    return {"id": page["id"], "url": page["url"]}


def _append_children(page_id: str, blocks: list[dict], headers: dict[str, str]) -> None:
    response = httpx.patch(
        f"{_API_BASE}/blocks/{page_id}/children",
        headers=headers,
        json={"children": blocks},
        timeout=30,
    )
    response.raise_for_status()


def get_block_children(block_id: str, headers: dict[str, str]) -> list[dict]:
    """block_id 바로 아래 자식 블록들을 순서대로 반환한다 (최대 100개, 로드맵 규모에선 충분)."""
    response = httpx.get(f"{_API_BASE}/blocks/{block_id}/children", headers=headers, timeout=30)
    response.raise_for_status()
    return response.json()["results"]


def get_block(block_id: str, headers: dict[str, str]) -> dict:
    response = httpx.get(f"{_API_BASE}/blocks/{block_id}", headers=headers, timeout=30)
    response.raise_for_status()
    return response.json()


def update_callout_text(block_id: str, content: str, headers: dict[str, str]) -> None:
    response = httpx.patch(
        f"{_API_BASE}/blocks/{block_id}",
        headers=headers,
        json={"callout": {"rich_text": [{"type": "text", "text": {"content": content}}]}},
        timeout=30,
    )
    response.raise_for_status()


def create_database(
    parent_page_id: str, title: str, properties: dict, headers: dict[str, str]
) -> dict:
    """데이터베이스를 만든다. {"database_id", "data_source_id"}를 반환한다.

    2025-09-03+ API부터 데이터베이스 아래에 "data source"가 별도 객체로 존재한다
    (SPRINT1_FEATURE4_ROADMAP_GENERATOR.md 9절 — 예전 task_database.py에서 실제 호출로 확인한 내용).
    행(page)의 parent는 database_id가 아니라 data_source_id여야 한다.
    """
    body = {
        "parent": {"type": "page_id", "page_id": parent_page_id},
        "title": [{"type": "text", "text": {"content": title}}],
        "initial_data_source": {"properties": properties},
    }
    response = httpx.post(f"{_API_BASE}/databases", headers=headers, json=body, timeout=30)
    response.raise_for_status()
    database = response.json()

    data_sources = database.get("data_sources") or []
    data_source_id = data_sources[0]["id"] if data_sources else database["id"]
    return {"database_id": database["id"], "data_source_id": data_source_id}


def create_database_row(
    data_source_id: str,
    properties: dict,
    headers: dict[str, str],
    blocks: list[dict] | None = None,
) -> dict:
    """데이터베이스 행(page)을 만든다. blocks는 그 행의 페이지 본문(예: task 상세 가이드)."""
    first_batch, remaining = (blocks or [])[:_MAX_BLOCKS_PER_REQUEST], (blocks or [])[
        _MAX_BLOCKS_PER_REQUEST:
    ]
    body = {
        "parent": {"type": "data_source_id", "data_source_id": data_source_id},
        "properties": properties,
        "children": first_batch,
    }
    response = httpx.post(f"{_API_BASE}/pages", headers=headers, json=body, timeout=30)
    response.raise_for_status()
    page = response.json()

    for i in range(0, len(remaining), _MAX_BLOCKS_PER_REQUEST):
        _append_children(page["id"], remaining[i : i + _MAX_BLOCKS_PER_REQUEST], headers)

    return {"id": page["id"], "url": page["url"]}


def query_data_source(data_source_id: str, headers: dict[str, str]) -> list[dict]:
    """data source(구 database) 안의 행을 전부 조회한다 (첫 페이지만, 최대 100건 — 부서 규모 전제라 충분).
    집계 콜아웃 새로고침(progress.py)에 쓴다. 공개 API는 서버 사이드 집계/차트가 없어 직접 세야 한다."""
    response = httpx.post(
        f"{_API_BASE}/data_sources/{data_source_id}/query", headers=headers, json={}, timeout=30
    )
    response.raise_for_status()
    return response.json()["results"]


def update_page_properties(page_id: str, properties: dict, headers: dict[str, str]) -> None:
    response = httpx.patch(
        f"{_API_BASE}/pages/{page_id}",
        headers=headers,
        json={"properties": properties},
        timeout=30,
    )
    response.raise_for_status()
