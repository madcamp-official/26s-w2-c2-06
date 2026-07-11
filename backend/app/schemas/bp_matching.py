"""
schemas/bp_matching.py

RAG 기반 BP 매칭 모듈(팀원 구현) → Opportunity 포맷팅 모듈(내 담당) 간
데이터 계약(contract)을 정의하는 스키마.

두 모듈은 이 파일을 공유해서 import한다.
스키마가 바뀌면 반드시 schema_version을 올리고 서로에게 알릴 것.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class BPMatchCase(BaseModel):
    """RAG 검색으로 찾은 개별 Best Practice 사례 1건

    주의: 리포트 출처는 Enum으로 고정하지 않는다. 리포트 개수는 계속 늘어나는
    "데이터"이지 "코드가 알아야 할 구조"가 아니다. 새 리포트를 추가할 때
    corpus_sources 테이블에 row만 넣으면 되고, 이 스키마/코드는 건드리지 않는다.

    corpus_sources 테이블 (Postgres, 별도 마이그레이션으로 관리):
        id            TEXT PRIMARY KEY   -- 예: "doc_004"
        title         TEXT               -- "kt cloud AX 트렌드 리포트"
        publisher     TEXT               -- "kt cloud"
        industry_tags TEXT[]             -- 필터링/추천 가중치에 사용
        published_at  DATE
        source_url    TEXT
    """

    source_document_id: str = Field(
        ..., description="corpus_sources 테이블의 id (예: 'doc_004')"
    )
    source_title: str = Field(
        ...,
        description="표시용 리포트 제목 (조인 없이 바로 렌더링하기 위한 비정규화 필드)",
    )
    case_title: str = Field(
        ..., description="사례 제목 (예: 'SK AX - 5% 성공기업 패턴')"
    )
    summary: str = Field(
        ...,
        description="사례 요약 2~3문장. 원문 그대로 넣지 말고 매칭 단계에서 이미 요약된 형태로 전달",
    )
    relevance_score: float = Field(
        ..., ge=0.0, le=1.0, description="쿼리와의 유사도 점수 (0~1)"
    )
    metric_snippet: str | None = Field(
        default=None,
        description="사례에 포함된 정량 수치가 있으면 그대로 (예: '업무시간 40% 감소'). 없으면 None",
    )


class BPMatchResult(BaseModel):
    """RAG 매칭 모듈의 최종 출력 — 다음 단계(포맷팅)로 이 형태 그대로 전달됨"""

    schema_version: str = "1.1"  # 1.0 -> 1.1: source_report Enum 제거, corpus_sources 참조 방식으로 변경
    task_id: str
    task_text: str = Field(
        ..., description="매칭에 사용된 원본 업무 설명 (Step1에서 수집된 텍스트)"
    )
    matched_cases: list[BPMatchCase] = Field(
        default_factory=list,
        description="관련도 순 정렬. 상위 3~5개만 반환하는 것을 권장 (전부 넘기지 않기)",
    )
    retrieved_at: datetime


# ── 아래는 팀원 구현 전에 내 쪽 개발을 시작하기 위한 더미 데이터 ──

DUMMY_MATCH_RESULT = BPMatchResult(
    task_id="task_0007",
    task_text="원자재 단가 자료 정리 후 주간 보고서 작성",
    matched_cases=[
        BPMatchCase(
            source_document_id="doc_003",
            source_title="Wrtn Technologies AX Report",
            case_title="Finance Agent 도입 성과",
            summary="재무 데이터 취합 및 보고서 작성을 자동화해 부서 총 근로시간을 40% 절감했다.",
            relevance_score=0.83,
            metric_snippet="FTE 40% 감소",
        ),
        BPMatchCase(
            source_document_id="doc_001",
            source_title="SK AX 리포트",
            case_title="AI 도입 성공 5% 기업의 공통 패턴",
            summary="성공 기업은 개별 PoC가 아닌 플랫폼 단위로 접근해 반복 업무의 자동화 범위를 넓혔다.",
            relevance_score=0.61,
            metric_snippet=None,
        ),
    ],
    retrieved_at=datetime.now(),
)

if __name__ == "__main__":
    # 팀원 구현이 끝나기 전에도 이 파일 하나로 내 쪽 포맷터 함수를 바로 테스트 가능
    print(DUMMY_MATCH_RESULT.model_dump_json(indent=2))