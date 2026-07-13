"""arXiv API 어댑터 (무료·키 불필요, Atom XML 응답).

논문 검색 → title/summary(abstract)/id(url)/published 수집. `source_type="research"`.
http://export.arxiv.org/api/query
"""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET

import httpx

from app.research.sources.base import RawSource

logger = logging.getLogger(__name__)

_ENDPOINT = "https://export.arxiv.org/api/query"
_NS = {"a": "http://www.w3.org/2005/Atom"}
_TIMEOUT = 10.0


def search(query: str, limit: int = 5) -> list[RawSource]:
    resp = httpx.get(
        _ENDPOINT,
        params={"search_query": f"all:{query}", "start": 0, "max_results": limit},
        timeout=_TIMEOUT,
        headers={"User-Agent": "ai-champion-research/0.1"},
        follow_redirects=True,
    )
    resp.raise_for_status()
    root = ET.fromstring(resp.text)

    out: list[RawSource] = []
    for entry in root.findall("a:entry", _NS):
        title = " ".join((entry.findtext("a:title", default="", namespaces=_NS) or "").split())
        if not title:
            continue
        url = (entry.findtext("a:id", default="", namespaces=_NS) or "").strip()
        abstract = " ".join(
            (entry.findtext("a:summary", default="", namespaces=_NS) or "").split()
        )
        published = (entry.findtext("a:published", default="", namespaces=_NS) or "")[:10] or None
        out.append(
            RawSource(
                title=title,
                url=url,
                abstract=abstract or None,
                source_type="research",
                published_date=published,
            )
        )
    return out
