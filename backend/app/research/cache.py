"""리서치 결과 캐시 (계약 §2.4).

동일 `goal_id` 재요청은 재검색 없이 이전 `ResearchContext`를 반환한다.
스프린트1은 프로세스 인메모리 캐시로 시작 (필요 시 이후 파일/DB로 승격).
`status="failed"` 결과는 캐싱하지 않는다 (다음 요청에서 재시도 가능하도록) — 이 규칙은 호출부(service)가 지킨다.
"""

from __future__ import annotations

from app.contracts import ResearchContext

_cache: dict[str, ResearchContext] = {}


def get(goal_id: str) -> ResearchContext | None:
    return _cache.get(goal_id)


def set(goal_id: str, ctx: ResearchContext) -> None:
    _cache[goal_id] = ctx


def clear() -> None:
    """테스트/재조사용."""
    _cache.clear()
