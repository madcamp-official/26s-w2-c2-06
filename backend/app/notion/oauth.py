"""
Notion Public Integration OAuth 흐름.

1. build_authorize_url(state)로 사용자를 Notion 인증 화면으로 보낸다 (state=account_id)
2. Notion이 redirect_uri로 ?code=...&state=...를 돌려주면 exchange_code_for_token(code)로 토큰 교환
3. list_shared_pages(access_token)로 이번에 공유된 페이지 후보 전체를 가져온다. 후보가 1개뿐이면
   바로 그 페이지를 기본 발행 대상으로 확정하고, 2개 이상이면 라우터가 선택 화면을 보여준다.

   (예전엔 "접근 가능한 첫 페이지"를 자동으로 골랐는데 — 어떤 페이지가 첫 번째로 오는지가
   Notion 검색 순위에 따라 달라져서, 재연결할 때마다 의도하지 않은 페이지가 발행 대상으로
   바뀌는 사고가 실 운영에서 반복됐다. 2026-07-15.)
"""

from urllib.parse import urlencode

import httpx

from app.core.config import settings

_AUTHORIZE_URL = "https://api.notion.com/v1/oauth/authorize"
_TOKEN_URL = "https://api.notion.com/v1/oauth/token"
_SEARCH_URL = "https://api.notion.com/v1/search"


def build_authorize_url(state: str) -> str:
    params = {
        "client_id": settings.notion_oauth_client_id,
        "redirect_uri": settings.notion_oauth_redirect_uri,
        "response_type": "code",
        "owner": "user",
        "state": state,
    }
    return f"{_AUTHORIZE_URL}?{urlencode(params)}"


def exchange_code_for_token(code: str) -> dict:
    response = httpx.post(
        _TOKEN_URL,
        auth=(settings.notion_oauth_client_id, settings.notion_oauth_client_secret),
        headers={"Content-Type": "application/json"},
        json={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": settings.notion_oauth_redirect_uri,
        },
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def _page_title(page: dict) -> str:
    title_items = page.get("properties", {}).get("title", {}).get("title", [])
    text = "".join(t.get("plain_text", "") for t in title_items)
    return text or "(제목 없음)"


def list_shared_pages(access_token: str) -> list[dict]:
    """이번 연결에서 integration과 공유된 페이지 후보 전체를 {"id", "title"} 형태로 반환한다."""
    response = httpx.post(
        _SEARCH_URL,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Notion-Version": settings.notion_api_version,
            "Content-Type": "application/json",
        },
        json={"filter": {"property": "object", "value": "page"}},
        timeout=30,
    )
    response.raise_for_status()
    results = response.json().get("results", [])
    return [{"id": page["id"], "title": _page_title(page)} for page in results]
