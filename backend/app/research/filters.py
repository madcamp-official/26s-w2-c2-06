"""소스 신뢰도 필터 · 요약 트림 · 수치 검증 (FEATURE3 §4, SPEC 2.6).

- `passes_url`: http(s) 실제 URL을 가진 소스만 통과.
- `sanitize_metric`: 숫자가 없는 metric_snippet은 인정하지 않고 None (수치 없는 서술의 오인용 방지).
- `trim_summary` / `first_sentence`: LLM 없이 abstract에서 요약/시사점을 뽑는 경량 처리.
  (원문 그대로가 아닌 완전 요약은 LLM 확보 시 승격 — 오픈 이슈)
"""

from __future__ import annotations

import re

_HAS_DIGIT = re.compile(r"\d")
_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")


def passes_url(url: str | None) -> bool:
    return bool(url) and url.strip().startswith(("http://", "https://"))


def sanitize_metric(snippet: str | None) -> str | None:
    if snippet is None:
        return None
    s = snippet.strip()
    if not s or not _HAS_DIGIT.search(s):
        return None
    return s


def trim_summary(text: str | None, max_sentences: int = 3, max_chars: int = 600) -> str:
    if not text:
        return ""
    sentences = _SENT_SPLIT.split(text.strip())
    out = " ".join(sentences[:max_sentences]).strip()
    return out[:max_chars]


def first_sentence(text: str | None, max_chars: int = 200) -> str:
    if not text:
        return ""
    return _SENT_SPLIT.split(text.strip())[0][:max_chars].strip()
