"""
contracts/research.py

3번(BP 리서치 엔진) -> 4번(로드맵 생성) 인터페이스. SPRINT1_CONTRACT.md 4절 스키마 그대로 코드화.
공동 소유 — 변경 시 SPRINT1_CONTRACT.md 8절 절차 따를 것. 실제 소유/구현은 3번 담당자(research/ 패키지).
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class ResearchStatus(str, Enum):
    OK = "ok"
    PARTIAL = "partial"
    FAILED = "failed"


class SourceType(str, Enum):
    TREND = "trend"
    RESEARCH = "research"
    PRACTICE = "practice"


class Finding(BaseModel):
    finding_id: str
    source_title: str
    source_url: str
    source_type: SourceType
    published_date: str | None = None
    summary: str
    relevant_method: str
    metric_snippet: str | None = None


class ResearchContext(BaseModel):
    goal_id: str
    retrieved_at: datetime
    status: ResearchStatus
    search_queries: list[str] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
