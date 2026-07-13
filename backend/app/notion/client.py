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
