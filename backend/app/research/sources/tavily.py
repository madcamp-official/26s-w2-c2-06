"""Tavily Search API 어댑터 (준무료 — 월 1,000 크레딧, 카드 불필요, `TAVILY_API_KEY` 필요).

AX 트렌드·블로그 등 범용 웹 결과 → `source_type="trend"`.
키가 없으면 빈 리스트를 반환한다(다른 소스로 degrade — 실패 계약과 동일한 정신).
https://docs.tavily.com/documentation/api-reference/endpoint/search
"""

from __future__ import annotations

import logging

import httpx

from app.core.config import settings
from app.research.sources.base import RawSource

logger = logging.getLogger(__name__)

_ENDPOINT = "https://api.tavily.com/search"
_TIMEOUT = 15.0


def search(query: str, limit: int = 5) -> list[RawSource]:
    api_key = settings.tavily_api_key
    if not api_key:
        logger.info("TAVILY_API_KEY 미설정 — tavily 소스 건너뜀")
        return []

    resp = httpx.post(
        _ENDPOINT,
        json={
            "query": query,
            "max_results": limit,
            "search_depth": "basic",
            "topic": "general",
        },
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        timeout=_TIMEOUT,
    )
    resp.raise_for_status()
    results = resp.json().get("results") or []

    out: list[RawSource] = []
    for r in results:
        title = (r.get("title") or "").strip()
        url = (r.get("url") or "").strip()
        if not title or not url:
            continue
        out.append(
            RawSource(
                title=title,
                url=url,
                abstract=(r.get("content") or None),
                source_type="trend",
                published_date=r.get("published_date"),
            )
        )
    return out
