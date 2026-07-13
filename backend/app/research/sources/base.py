"""소스 어댑터 공통 타입."""

from __future__ import annotations

from dataclasses import dataclass

from app.contracts.research import SourceType


@dataclass
class RawSource:
    """어댑터가 반환하는 원시 소스 1건. service가 `Finding`으로 매핑한다."""

    title: str
    url: str
    abstract: str | None
    source_type: SourceType
    published_date: str | None = None  # 발행연도/일자 (모르면 None)
    metric_snippet: str | None = None  # 어댑터가 검증된 수치를 줄 때만 (논문은 보통 None)
