"""Semantic Scholar Graph API 어댑터 (무료·키 불필요, rate limit만 존재).

논문 검색 → title/abstract/url/year 수집. `source_type="research"`.
https://api.semanticscholar.org/graph/v1/paper/search
"""

from __future__ import annotations

import logging

import httpx

from app.research.sources.base import RawSource

logger = logging.getLogger(__name__)

_ENDPOINT = "https://api.semanticscholar.org/graph/v1/paper/search"
_FIELDS = "title,abstract,url,year,paperId"
_TIMEOUT = 10.0


def search(query: str, limit: int = 5) -> list[RawSource]:
    resp = httpx.get(
        _ENDPOINT,
        params={"query": query, "limit": limit, "fields": _FIELDS},
        timeout=_TIMEOUT,
        headers={"User-Agent": "ai-champion-research/0.1"},
        follow_redirects=True,
    )
    resp.raise_for_status()
    data = resp.json().get("data") or []

    out: list[RawSource] = []
    for p in data:
        title = (p.get("title") or "").strip()
        if not title:
            continue
        url = (p.get("url") or "").strip()
        if not url and p.get("paperId"):
            url = f"https://www.semanticscholar.org/paper/{p['paperId']}"
        year = p.get("year")
        out.append(
            RawSource(
                title=title,
                url=url,
                abstract=(p.get("abstract") or None),
                source_type="research",
                published_date=str(year) if year else None,
            )
        )
    return out
