"""GitHub Search API 어댑터 (무료, 토큰 옵션).

frontier 개인/현장의 실제 활용 도구·프롬프트·자동화 저장소를 검색 → `source_type="practice"`.
인증 없이도 동작(검색 엔드포인트 10회/분). `GITHUB_TOKEN` 있으면 30회/분로 상향.
https://docs.github.com/en/rest/search/search#search-repositories
"""

from __future__ import annotations

import logging

import httpx

from app.core.config import settings
from app.research.sources.base import RawSource

logger = logging.getLogger(__name__)

_ENDPOINT = "https://api.github.com/search/repositories"
_TIMEOUT = 10.0


def search(query: str, limit: int = 5) -> list[RawSource]:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "ai-champion-research/0.1",
    }
    if settings.github_token:
        headers["Authorization"] = f"Bearer {settings.github_token}"

    resp = httpx.get(
        _ENDPOINT,
        params={"q": query, "sort": "stars", "order": "desc", "per_page": limit},
        timeout=_TIMEOUT,
        headers=headers,
        follow_redirects=True,
    )
    resp.raise_for_status()
    items = resp.json().get("items") or []

    out: list[RawSource] = []
    for repo in items:
        title = (repo.get("full_name") or "").strip()
        url = (repo.get("html_url") or "").strip()
        if not title or not url:
            continue
        description = (repo.get("description") or "").strip() or None
        stars = repo.get("stargazers_count")
        # stars는 인기도 신호일 뿐 AX 효과 수치가 아니므로 metric_snippet에 넣지 않고
        # abstract에 부기해 요약 단계에서 신뢰도 맥락으로만 쓰이게 한다.
        if description and isinstance(stars, int) and stars > 0:
            description = f"{description} (GitHub {stars} stars)"
        out.append(
            RawSource(
                title=title,
                url=url,
                abstract=description,
                source_type="practice",
                published_date=(repo.get("pushed_at") or "")[:10] or None,
                metric_snippet=None,
            )
        )
    return out
