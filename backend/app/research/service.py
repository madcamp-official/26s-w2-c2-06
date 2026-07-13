"""run_research — 기능 3의 유일한 진입점 (계약 §2.3).

흐름: 캐시 조회 → 쿼리 빌드 → 큐레이션 seed 병합 → (쿼리×어댑터) 실시간 조회
     → 신뢰도 필터·중복 제거 → status 판정 → 캐시 저장 → ResearchContext 반환.

검색 백엔드는 다중 소스 실시간 API (계약 v0.4 §2.5, 스프린트1: Semantic Scholar + arXiv).
LLM(Gemini) 불필요 — 핵심 경로에 외부 모델 호출이 없다.

**실패 계약 (계약 §4):** 어떤 실패에도 경계 밖으로 예외를 던지지 않는다.
모든 소스가 실패하거나 쓸 만한 결과가 없으면 status="failed" + 빈 findings를 반환한다.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.contracts import Finding, GoalDefinition, ResearchContext
from app.research import cache
from app.research.filters import first_sentence, passes_url, sanitize_metric, trim_summary
from app.research.query_builder import build_search_queries
from app.research.seed import load_seed_findings
from app.research.sources import arxiv, semantic_scholar

logger = logging.getLogger(__name__)

# 실시간 소스 어댑터 (각각 search(query, limit) -> list[RawSource])
ADAPTERS = [semantic_scholar, arxiv]

MAX_FINDINGS = 8  # 계약 §4: 목표 3~8건
OK_THRESHOLD = 3  # 3건 이상 ok, 1~2건 partial, 0건 failed
PER_QUERY_LIMIT = 4


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

        # 1) 큐레이션 seed findings (계약 §2.6) — 실시간 결과보다 앞에 병합
        for sd in load_seed_findings(goal_id):
            url = (sd.get("source_url") or "").strip()
            title = (sd.get("source_title") or "").strip()
            summary = (sd.get("summary") or "").strip()
            if not (url and title and summary):
                continue  # 불완전 seed는 건너뜀 (실패 계약: 예외 없이 skip)
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

        # 2) 실시간 소스 조회 (쿼리 × 어댑터). 개별 실패는 흡수하고 계속
        for query in queries:
            if len(collected) >= MAX_FINDINGS:
                break
            for adapter in ADAPTERS:
                if len(collected) >= MAX_FINDINGS:
                    break
                try:
                    raws = adapter.search(query, limit=PER_QUERY_LIMIT)
                except Exception as exc:
                    # 개별 소스의 일시 실패(429/타임아웃 등)는 다른 소스로 흡수 — 전체 traceback 대신 경고
                    logger.warning("source failed: %s query=%r (%s)", adapter.__name__, query, exc)
                    continue
                for rs in raws:
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
