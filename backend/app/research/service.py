"""run_research — 기능 3의 유일한 진입점 (계약 §2.3).

흐름: 캐시 조회 → 쿼리 빌드 → 큐레이션 seed 병합 → (쿼리×pillar) 실시간 조회
     → 신뢰도 필터·중복 제거 → status 판정 → 캐시 저장 → ResearchContext 반환.

검색 백엔드는 다중 소스 실시간 API (계약 v0.5 §2.7: Semantic Scholar·arXiv·GitHub·Tavily).
LLM(Gemini) 불필요 — 핵심 경로에 외부 모델 호출이 없다.

**실무 적합도 우선순위 + 다양성 보장 (계약 v0.6 §2.7 변경):** 예전엔 어댑터를
`semantic_scholar → arxiv → github → tavily` 순으로 끝까지 채우는 방식이라, 논문 소스
(semantic_scholar+arxiv) 둘만으로 MAX_FINDINGS가 다 차버리면 practice(GitHub)·trend(Tavily)가
같은 요청 안에서 한 번도 반영되지 못하는 문제가 있었다. 지금은 SPEC 4.3의 세 조사 대상
(practice/trend/research)을 "pillar"로 묶어 쿼리마다 매 pillar에서 한 건씩 라운드로빈으로
채택한다(PILLARS 순서 = practice → trend → research, 동률일 때 실무 근거를 우선 채택).
LLM 판단 없이 규칙만으로 동작해 계약 §2.5(핵심 경로 LLM 불필요)를 그대로 지킨다.

**실패 계약 (계약 §4):** 어떤 실패에도 경계 밖으로 예외를 던지지 않는다.
모든 소스가 실패하거나 쓸 만한 결과가 없으면 status="failed" + 빈 findings를 반환한다.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from itertools import zip_longest
from typing import Any

from app.contracts import Finding, GoalDefinition, ResearchContext
from app.research import cache
from app.research.filters import first_sentence, passes_url, sanitize_metric, trim_summary
from app.research.query_builder import build_search_queries
from app.research.seed import load_seed_findings
from app.research.sources import arxiv, github, semantic_scholar, tavily
from app.research.sources.base import RawSource

logger = logging.getLogger(__name__)

# 실시간 소스를 SPEC 4.3의 세 조사 대상(pillar)으로 묶는다. 같은 pillar 안 여러 어댑터
# (research = 논문 API 2종)는 단순 연결하고, pillar 간에는 라운드로빈으로 한 건씩 채택한다
# (_roundrobin). 리스트 순서가 동률 상황의 우선순위 = 실무 적합도 가중치(practice > trend > research).
PILLARS: list[tuple[str, list[Any]]] = [
    ("practice", [github]),
    ("trend", [tavily]),
    ("research", [semantic_scholar, arxiv]),
]

MAX_FINDINGS = 8  # 계약 §4: 목표 3~8건
OK_THRESHOLD = 3  # 3건 이상 ok, 1~2건 partial, 0건 failed
PER_QUERY_LIMIT = 4
SEED_LIMIT = 4  # 계약 §2.6: seed는 "소수"로 제한 — 실시간 조회가 주 메커니즘으로 남도록 상한


def _roundrobin(*iterables: list[RawSource]):
    """여러 리스트를 한 건씩 번갈아 합친다 (앞쪽 리스트가 동률 시 우선). 표준 itertools 레시피."""
    sentinel = object()
    for combo in zip_longest(*iterables, fillvalue=sentinel):
        for item in combo:
            if item is not sentinel:
                yield item


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _failed(goal_id: str, queries: list[str] | None = None) -> ResearchContext:
    return ResearchContext(
        goal_id=goal_id,
        retrieved_at=_now(),
        status="failed",
        search_queries=queries or [],
        findings=[],
    )


def run_research(goal: GoalDefinition) -> ResearchContext:
    goal_id = goal.goal_id
    try:
        cached = cache.get(goal_id)
        if cached is not None:
            logger.info("research cache hit: goal_id=%s", goal_id)
            return cached

        queries = build_search_queries(goal)
        collected: list[Finding] = []
        seen_urls: set[str] = set()

        def _add(
            *,
            title: str,
            url: str,
            source_type: str,
            summary: str,
            relevant_method: str,
            published_date: str | None,
            metric_snippet: str | None,
        ) -> bool:
            """중복 아니면 Finding 추가. MAX 도달 시 False."""
            if url in seen_urls:
                return len(collected) < MAX_FINDINGS
            seen_urls.add(url)
            collected.append(
                Finding(
                    finding_id=f"F{len(collected) + 1}",
                    source_title=title,
                    source_url=url,
                    source_type=source_type,
                    published_date=published_date,
                    summary=summary,
                    relevant_method=relevant_method,
                    metric_snippet=sanitize_metric(metric_snippet),
                )
            )
            return len(collected) < MAX_FINDINGS

        # 1) 큐레이션 seed findings (계약 §2.6) — 실시간 결과보다 앞에 병합.
        #    seed는 "소수"로 제한(SEED_LIMIT) — 파일에 더 있어도 실시간 조회가 주 메커니즘으로 남도록 상한을 둔다.
        seed_used = 0
        for sd in load_seed_findings(goal_id):
            if seed_used >= SEED_LIMIT:
                break
            url = (sd.get("source_url") or "").strip()
            title = (sd.get("source_title") or "").strip()
            summary = (sd.get("summary") or "").strip()
            if not (url and title and summary):
                continue  # 불완전 seed는 건너뜀 (실패 계약: 예외 없이 skip)
            seed_used += 1
            if not _add(
                title=title,
                url=url,
                source_type=sd.get("source_type") or "practice",
                summary=summary,
                relevant_method=(sd.get("relevant_method") or "").strip() or title,
                published_date=sd.get("published_date"),
                metric_snippet=sd.get("metric_snippet"),
            ):
                break

        # 2) 실시간 소스 조회 (쿼리 × pillar). 개별 어댑터 실패는 흡수하고 계속.
        #    pillar 간 라운드로빈으로 다양성을 보장한다 (모듈 docstring 참고).
        for query in queries:
            if len(collected) >= MAX_FINDINGS:
                break

            pillar_lists: list[list[RawSource]] = []
            for pillar_name, adapters in PILLARS:
                items: list[RawSource] = []
                for adapter in adapters:
                    try:
                        items.extend(adapter.search(query, limit=PER_QUERY_LIMIT))
                    except Exception as exc:
                        # 개별 소스의 일시 실패(429/타임아웃 등)는 다른 소스로 흡수 — 전체 traceback 대신 경고
                        logger.warning("source failed: %s query=%r (%s)", adapter.__name__, query, exc)
                pillar_lists.append(items)

            for rs in _roundrobin(*pillar_lists):
                if len(collected) >= MAX_FINDINGS:
                    break
                if not passes_url(rs.url):
                    continue
                summary = trim_summary(rs.abstract) or rs.title
                method = first_sentence(rs.abstract) or rs.title
                if not _add(
                    title=rs.title,
                    url=rs.url,
                    source_type=rs.source_type,
                    summary=summary,
                    relevant_method=method,
                    published_date=rs.published_date,
                    metric_snippet=rs.metric_snippet,
                ):
                    break

        if not collected:
            logger.warning("research produced no findings: goal_id=%s", goal_id)
            return _failed(goal_id, queries)  # 캐싱하지 않음 (재시도 허용)

        status = "ok" if len(collected) >= OK_THRESHOLD else "partial"
        ctx = ResearchContext(
            goal_id=goal_id,
            retrieved_at=_now(),
            status=status,
            search_queries=queries,
            findings=collected,
        )
        cache.set(goal_id, ctx)  # 성공 결과만 캐싱 (계약 §2.4)
        return ctx

    except Exception:
        # 어떤 예외도 경계 밖으로 나가지 않는다 (실패 계약)
        logger.exception("run_research hard failure: goal_id=%s", goal_id)
        return _failed(goal_id)
