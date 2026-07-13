"""
Notion Public Integration OAuth 흐름.

1. build_authorize_url(state)로 사용자를 Notion 인증 화면으로 보낸다 (state=account_id)
2. Notion이 redirect_uri로 ?code=...&state=...를 돌려주면 exchange_code_for_token(code)로 토큰 교환
3. find_default_page_id(access_token)로 이번에 공유된 페이지 중 하나를 기본 발행 대상으로 잡는다
   (v1 단순화: 접근 가능한 첫 페이지. 여러 페이지 중 선택하는 UI는 추후 과제)
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


def find_default_page_id(access_token: str) -> str | None:
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
    return results[0]["id"] if results else None
