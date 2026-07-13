"""ResearchContext / Finding — 3 → 4 인터페이스 계약 스키마 (계약 §4).

기능 3(BP 리서치 엔진)의 출력. 기능 4(로드맵 생성)가 `finding_id`로 근거를 인용한다.

**규약 (계약 §4)**
- `findings`는 목표 단위 조사 결과. 목표 3~8건.
- `status`: "ok"(정상) / "partial"(일부만 확보) / "failed"(검색 실패, findings 빈 배열).
- 실패 계약: 검색 실패 시 예외를 던지지 않고 status="failed" + 빈 findings 반환.
- `search_queries`는 디버깅·출처 추적용 — 사용자에게 노출하지 않는다.
- 사용자 노출 금지 (SPEC 4.3). 출처 인용의 원천은 `source_url` + `metric_snippet`뿐.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

ResearchStatus = Literal["ok", "partial", "failed"]
SourceType = Literal["trend", "research", "practice"]


class Finding(BaseModel):
    """목표와 관련해 조사된 개별 근거 1건 (외부 소스 1개에 대응)."""

    finding_id: str = Field(
        ..., description="근거 식별자 (예: 'F1'). 기능 4가 source_refs로 참조 — 인덱스 참조 금지"
    )
    source_title: str = Field(..., description="출처 제목")
    source_url: str = Field(
        ..., description="출처 URL. grounding metadata에서 추출된 실제 URL만 사용"
    )
    source_type: SourceType = Field(
        ..., description="trend(트렌드) / research(논문·연구) / practice(개인·현장 활용법)"
    )
    published_date: str | None = Field(
        default=None, description="발행일 (모르면 null). 문자열 형태 예: '2026-05-01'"
    )
    summary: str = Field(..., description="2~3문장 요약 (원문 그대로 X, 요약된 형태)")
    relevant_method: str = Field(
        ..., description="목표와 연결되는 방법/시사점 (예: 'LLM 위키 활성화 조건')"
    )
    metric_snippet: str | None = Field(
        default=None,
        description="출처가 확인된 정량 수치만 (예: '업무시간 40% 감소'). 없으면 null",
    )


class ResearchContext(BaseModel):
    """기능 3의 최종 출력 — `generate_roadmap()`으로 이 형태 그대로 전달된다."""

    goal_id: str = Field(..., description="입력 GoalDefinition.goal_id 그대로 전달")
    retrieved_at: datetime = Field(..., description="리서치 수행 시각 (UTC)")
    status: ResearchStatus = Field(..., description="ok / partial / failed")
    search_queries: list[str] = Field(
        default_factory=list, description="사용한 검색 쿼리 (디버깅·추적용, 사용자 비노출)"
    )
    findings: list[Finding] = Field(
        default_factory=list, description="조사 결과 (목표 3~8건). failed 시 빈 배열"
    )
