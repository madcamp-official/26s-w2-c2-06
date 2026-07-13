"""소스 어댑터 — 요청 시점 실시간 외부 조회 (계약 v0.4 §2.5).

각 어댑터는 `search(query, limit) -> list[RawSource]` 하나를 제공한다.
스프린트1 범위: 논문 API (Semantic Scholar + arXiv). 키 불필요·완전 무료.
어댑터는 예외를 던질 수 있다 — 실패 계약(예외 흡수)은 상위 `service.run_research`가 책임진다.
"""

from app.research.sources.base import RawSource

__all__ = ["RawSource"]
