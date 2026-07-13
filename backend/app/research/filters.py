"""소스 신뢰도 필터 & 수치 검증 (FEATURE3 §4-4, SPEC 2.6 '출처 있는 경우만 인용').

스프린트1은 경량 필터:
- `passes_trust_filter`: 유효한 http(s) URL을 가진 소스만 통과 (grounding이 준 실제 URL).
- `sanitize_metric`: 수치(숫자)가 없는 metric_snippet은 인정하지 않고 None으로 (수치 없는 서술을 metric으로 오인용 방지).
소스 신뢰도 기준 고도화(도메인 블록리스트 등)는 오픈 이슈로 남긴다.
"""

from __future__ import annotations

import re

from app.research.gemini_client import Source

_HAS_DIGIT = re.compile(r"\d")


def passes_trust_filter(source: Source) -> bool:
    url = (source.url or "").strip()
    return url.startswith(("http://", "https://"))


def sanitize_metric(snippet: str | None) -> str | None:
    """수치가 포함된 경우에만 metric_snippet으로 인정. 그 외에는 None."""
    if snippet is None:
        return None
    s = snippet.strip()
    if not s or not _HAS_DIGIT.search(s):
        return None
    return s
