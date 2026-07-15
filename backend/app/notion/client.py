"""Notion REST 호출 (공식 SDK 미사용). 인증은 호출하는 쪽에서 headers로 넘긴다 —
계정마다 다른 access_token을 쓰므로 이 모듈은 특정 계정을 알지 못한다 (app/notion/publish.py 참고)."""

import httpx

_API_BASE = "https://api.notion.com/v1"
_MAX_BLOCKS_PER_REQUEST = 100


def _raise_for_status(response: httpx.Response) -> None:
    """httpx의 기본 raise_for_status()는 응답 본문(Notion이 돌려주는 구체적인 사유,
    예: "x_axis.type should be ...")을 예외 메시지에 담지 않아 서버 로그만 봐서는 원인을
    알 수 없다 — Notion의 에러 바디를 그대로 붙여 다시 던진다."""
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as e:
        try:
            detail = response.json()
        except ValueError:
            detail = response.text
        raise httpx.HTTPStatusError(f"{e} -> {detail}", request=e.request, response=e.response) from e


def create_page(
    parent_page_id: str,
    title: str,
    blocks: list[dict],
    headers: dict[str, str],
    icon: str | None = None,
    cover_url: str | None = None,
) -> dict:
    """blocks[:100]으로 페이지를 만들고, 나머지는 이어붙인다. {"id", "url"}을 반환한다.
    icon(이모지 한 글자)·cover_url(외부 이미지 URL)을 주면 각각 페이지 아이콘·배너로 설정한다
    — 둘 다 실제 API 호출로 지원 확인됨."""
    first_batch, remaining = blocks[:_MAX_BLOCKS_PER_REQUEST], blocks[_MAX_BLOCKS_PER_REQUEST:]

    body = {
        "parent": {"type": "page_id", "page_id": parent_page_id},
        "properties": {"title": {"title": [{"type": "text", "text": {"content": title}}]}},
        "children": first_batch,
    }
    if icon:
        body["icon"] = {"type": "emoji", "emoji": icon}
    if cover_url:
        body["cover"] = {"type": "external", "external": {"url": cover_url}}
    response = httpx.post(f"{_API_BASE}/pages", headers=headers, json=body, timeout=30)
    _raise_for_status(response)
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
    _raise_for_status(response)


def get_block_children(block_id: str, headers: dict[str, str]) -> list[dict]:
    """block_id 바로 아래 자식 블록들을 순서대로 반환한다 (최대 100개, 로드맵 규모에선 충분)."""
    response = httpx.get(f"{_API_BASE}/blocks/{block_id}/children", headers=headers, timeout=30)
    _raise_for_status(response)
    return response.json()["results"]


def get_block(block_id: str, headers: dict[str, str]) -> dict:
    response = httpx.get(f"{_API_BASE}/blocks/{block_id}", headers=headers, timeout=30)
    _raise_for_status(response)
    return response.json()


def update_callout_text(block_id: str, content: str, headers: dict[str, str]) -> None:
    response = httpx.patch(
        f"{_API_BASE}/blocks/{block_id}",
        headers=headers,
        json={"callout": {"rich_text": [{"type": "text", "text": {"content": content}}]}},
        timeout=30,
    )
    _raise_for_status(response)


def create_database(
    parent_page_id: str, title: str, properties: dict, headers: dict[str, str]
) -> dict:
    """데이터베이스를 만든다. {"database_id", "data_source_id"}를 반환한다.

    2025-09-03+ API부터 데이터베이스 아래에 "data source"가 별도 객체로 존재한다
    (SPRINT1_FEATURE4_ROADMAP_GENERATOR.md 9절 — 예전 task_database.py에서 실제 호출로 확인한 내용).
    행(page)의 parent는 database_id가 아니라 data_source_id여야 한다.

    `is_inline: true`로 만들어 부모 페이지에 표(행이 바로 보이는 인라인 테이블)로 붙는다 —
    이걸 안 주면 Notion 기본값은 "링크만 있고 클릭해야 열리는" 축소 카드라 대시보드가 밋밋해
    보인다(실제 호출로 확인, 2026-07-15).
    """
    body = {
        "parent": {"type": "page_id", "page_id": parent_page_id},
        "title": [{"type": "text", "text": {"content": title}}],
        "is_inline": True,
        "initial_data_source": {"properties": properties},
    }
    response = httpx.post(f"{_API_BASE}/databases", headers=headers, json=body, timeout=30)
    _raise_for_status(response)
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
    _raise_for_status(response)
    page = response.json()

    for i in range(0, len(remaining), _MAX_BLOCKS_PER_REQUEST):
        _append_children(page["id"], remaining[i : i + _MAX_BLOCKS_PER_REQUEST], headers)

    return {"id": page["id"], "url": page["url"]}


def get_data_source(data_source_id: str, headers: dict[str, str]) -> dict:
    """데이터소스 스키마를 조회한다. dual relation 생성 직후 자동 부여된 역방향 속성의
    실제 이름/ID를 찾을 때 쓴다(생성 시점엔 이 이름을 지정할 방법이 없다 — 실 API 호출로 확인)."""
    response = httpx.get(f"{_API_BASE}/data_sources/{data_source_id}", headers=headers, timeout=30)
    _raise_for_status(response)
    return response.json()


def update_data_source_properties(
    data_source_id: str, properties: dict, headers: dict[str, str]
) -> dict:
    """데이터소스 생성 후 속성을 추가·수정한다 (역방향 relation 개명, rollup 추가 등)."""
    response = httpx.patch(
        f"{_API_BASE}/data_sources/{data_source_id}",
        headers=headers,
        json={"properties": properties},
        timeout=30,
    )
    _raise_for_status(response)
    return response.json()


def update_view_configuration(view_id: str, configuration: dict, headers: dict[str, str]) -> dict:
    """뷰(표 등)의 표시 설정을 바꾼다 — 지금은 표 뷰의 컬럼 순서(sync.py `_set_table_column_order`)
    에만 쓰인다. 차트 뷰를 만드는 데도 쓸 수 있지만(`"type": "chart", "chart_type": ...`), 이
    앱은 차트 자동 생성을 하지 않는다(모듈 docstring 참고 — 대시보드는 유료 플랜 전용, 개별
    차트 뷰는 API가 linked database를 지원하지 않아 원하는 배치를 낼 수 없어 뺐다)."""
    response = httpx.patch(
        f"{_API_BASE}/views/{view_id}", headers=headers, json={"configuration": configuration}, timeout=30
    )
    _raise_for_status(response)
    return response.json()


def update_view_sorts(view_id: str, sorts: list[dict], headers: dict[str, str]) -> dict:
    """뷰에 저장 정렬을 건다(예: 표 뷰의 행 순서). "configuration"이 아니라 view 객체 최상위 필드다."""
    response = httpx.patch(f"{_API_BASE}/views/{view_id}", headers=headers, json={"sorts": sorts}, timeout=30)
    _raise_for_status(response)
    return response.json()


def list_views(database_id: str, headers: dict[str, str]) -> list[dict]:
    """database_id에 딸린 뷰 참조(minimal, {"object","id"}만) 목록을 반환한다. `create_database`
    직후 호출하면 자동 생성된 기본 "Table" 뷰 하나뿐이라, 그 뷰의 컬럼 순서·정렬을
    `update_view_configuration`으로 이어서 조정할 때(sync.py) 대상 view_id를 찾는 데 쓴다."""
    response = httpx.get(f"{_API_BASE}/views", headers=headers, params={"database_id": database_id}, timeout=30)
    _raise_for_status(response)
    return response.json()["results"]


def query_data_source(data_source_id: str, headers: dict[str, str]) -> list[dict]:
    """data source(구 database) 안의 행을 전부 조회한다 (첫 페이지만, 최대 100건 — 부서 규모 전제라 충분).
    집계 콜아웃 새로고침(progress.py)에 쓴다. 공개 API는 서버 사이드 집계/차트가 없어 직접 세야 한다."""
    response = httpx.post(
        f"{_API_BASE}/data_sources/{data_source_id}/query", headers=headers, json={}, timeout=30
    )
    _raise_for_status(response)
    return response.json()["results"]


def update_page_properties(page_id: str, properties: dict, headers: dict[str, str]) -> None:
    response = httpx.patch(
        f"{_API_BASE}/pages/{page_id}",
        headers=headers,
        json={"properties": properties},
        timeout=30,
    )
    _raise_for_status(response)
