"""Notion 페이지 생성 REST 호출 (공식 SDK 미사용). 인증은 호출하는 쪽에서 headers로 넘긴다 —
계정마다 다른 access_token을 쓰므로 이 모듈은 특정 계정을 알지 못한다 (app/notion/publish.py 참고)."""

import httpx

_API_BASE = "https://api.notion.com/v1"
_MAX_BLOCKS_PER_REQUEST = 100


def create_page(parent_page_id: str, title: str, blocks: list[dict], headers: dict[str, str]) -> str:
    """blocks[:100]으로 페이지를 만들고, 나머지는 이어붙여서 최종 Notion 페이지 URL을 반환한다."""
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

    return page["url"]


def _append_children(page_id: str, blocks: list[dict], headers: dict[str, str]) -> None:
    response = httpx.patch(
        f"{_API_BASE}/blocks/{page_id}/children",
        headers=headers,
        json={"children": blocks},
        timeout=30,
    )
    response.raise_for_status()
