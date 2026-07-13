"""RoadmapResult 캐시. `app/research/cache.py`와 동일한 패턴(goal_id 키, 인메모리)을 따른다.

동일 goal_id 재요청 시 Gemini Stage A+B 재호출(약 55~60초 + 무료 티어 할당량 소모)을
건너뛴다. 팀원이 SPRINT1_CONTRACT.md §2.4 "오픈 제안"으로 남긴 항목 — 기능 4(로드맵 생성)
담당 소관이라 이 모듈에서 구현한다.

주의: research/cache.py와 마찬가지로 캐시 키는 goal_id뿐이다. 같은 goal_id로 onboarding
데이터를 바꿔서 재요청해도 첫 결과가 그대로 반환된다 (실제로 흔한 시나리오는 아니라고 판단).
"""

from app.contracts.roadmap import RoadmapResult

_cache: dict[str, RoadmapResult] = {}


def get(goal_id: str) -> RoadmapResult | None:
    return _cache.get(goal_id)


def set(goal_id: str, result: RoadmapResult) -> None:
    _cache[goal_id] = result


def clear() -> None:
    """테스트/강제 재생성용."""
    _cache.clear()
