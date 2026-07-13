"""Gemini 호출 래퍼 — 그라운딩 검색 + 구조화 (FEATURE3 §4-2,3).

두 단계로 나눈다 (도구 사용과 structured output을 한 호출에 섞지 않기 위함):
1. `grounded_search(query)`  — Google Search grounding으로 웹 조사. 응답 텍스트 + 실제 소스(URL/제목)를
   grounding metadata에서 추출.
2. `structure_findings(...)` — 조사 텍스트 + 실제 소스 목록을 받아 findings JSON으로 구조화
   (response_schema로 JSON 강제, 도구 없음). source_url/title은 모델이 만들지 않고 실제 소스에서 매핑한다.

키는 `GEMINI_API_KEY_RESEARCH`만 읽는다 (계약 §6, 교차 참조 금지). 하드코딩 금지.
이 모듈은 예외를 던질 수 있다 — 실패 계약(예외 삼키기)은 상위 `service.run_research`가 책임진다.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from google import genai
from google.genai import types
from pydantic import BaseModel

from app.core.config import settings
from app.contracts.research import SourceType

logger = logging.getLogger(__name__)

_client: genai.Client | None = None


def _model() -> str:
    # env(GEMINI_RESEARCH_MODEL)로 오버라이드 가능. 계정별 사용 가능 모델 차이 대응.
    return settings.gemini_research_model or "gemini-flash-latest"


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        key = settings.gemini_api_key_research
        if not key:
            raise RuntimeError(
                "GEMINI_API_KEY_RESEARCH가 설정되지 않았습니다 (docs/setup/API_KEY_SETUP.md 참고)"
            )
        _client = genai.Client(api_key=key)
    return _client


@dataclass
class Source:
    """grounding metadata에서 추출한 실제 웹 소스 1개."""

    title: str
    url: str
    domain: str | None = None


@dataclass
class GroundedResult:
    text: str
    sources: list[Source] = field(default_factory=list)


def grounded_search(query: str) -> GroundedResult:
    """Google Search grounding으로 쿼리를 조사하고, 응답 텍스트 + 실제 소스 목록을 반환."""
    client = _get_client()
    resp = client.models.generate_content(
        model=_model(),
        contents=(
            "다음 주제를 실제 웹 검색으로 조사해, 핵심 사실·방법·시사점을 3~6문장으로 요약하라. "
            "가능하면 출처가 분명한 정량 수치를 포함하라. 광고성·근거 없는 주장은 제외한다.\n\n"
            f"주제: {query}"
        ),
        config=types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())],
            temperature=0.2,
        ),
    )

    text = (resp.text or "").strip()

    sources: list[Source] = []
    seen: set[str] = set()
    candidates = resp.candidates or []
    gm = getattr(candidates[0], "grounding_metadata", None) if candidates else None
    chunks = getattr(gm, "grounding_chunks", None) or []
    for ch in chunks:
        web = getattr(ch, "web", None)
        uri = getattr(web, "uri", None) if web else None
        if not uri or not uri.startswith("http"):
            continue
        if uri in seen:
            continue
        seen.add(uri)
        sources.append(
            Source(
                title=(getattr(web, "title", None) or uri),
                url=uri,
                domain=getattr(web, "domain", None),
            )
        )

    return GroundedResult(text=text, sources=sources)


class StructuredFinding(BaseModel):
    """구조화 단계 출력 1건. `source_index`는 넘겨준 소스 목록의 인덱스."""

    source_index: int
    source_type: SourceType
    summary: str
    relevant_method: str
    metric_snippet: str | None = None


class _StructuredFindings(BaseModel):
    findings: list[StructuredFinding]


def structure_findings(
    goal_text: str,
    query: str,
    report_text: str,
    sources: list[Source],
) -> list[StructuredFinding]:
    """조사 텍스트 + 실제 소스 목록을 findings로 구조화. 소스가 없으면 빈 리스트."""
    if not sources:
        return []

    client = _get_client()
    source_block = "\n".join(f"[{i}] {s.title} — {s.url}" for i, s in enumerate(sources))

    prompt = (
        "너는 리서치 정리 담당이다. 아래 '조사 요약'과 '소스 목록'을 바탕으로, "
        "'목표'와 관련 있는 소스에 대해서만 findings 항목을 만들어라.\n"
        "규칙:\n"
        "- 각 finding의 source_index는 반드시 아래 소스 목록의 번호를 그대로 쓴다 (새 번호/URL을 지어내지 말 것).\n"
        "- summary: 2~3문장, 한국어, 원문 복붙 금지(요약).\n"
        "- relevant_method: 이 소스가 목표에 주는 방법/시사점 한 줄.\n"
        "- source_type: trend(트렌드/일반 아티클) / research(논문·연구·리포트) / practice(개인·현장 실제 활용법) 중 하나.\n"
        "- metric_snippet: 조사 요약에 '출처가 분명한 정량 수치'가 있을 때만 그 수치를 그대로. 없으면 null. 지어내지 말 것.\n"
        "- 목표와 무관하거나 근거가 빈약한 소스는 제외한다.\n\n"
        f"목표: {goal_text}\n"
        f"조사 관점(쿼리): {query}\n\n"
        f"조사 요약:\n{report_text}\n\n"
        f"소스 목록:\n{source_block}\n"
    )

    resp = client.models.generate_content(
        model=_model(),
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=_StructuredFindings,
            temperature=0.2,
        ),
    )

    parsed = getattr(resp, "parsed", None)
    if parsed is None:
        parsed = _StructuredFindings.model_validate_json((resp.text or "").strip())
    return list(parsed.findings)
