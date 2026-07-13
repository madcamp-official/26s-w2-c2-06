"""run_research — 기능 3의 유일한 진입점 (계약 §2.3).

흐름: 캐시 조회 → 쿼리 빌드 → (관점별) grounding 검색 + 구조화 → 신뢰도 필터·중복 제거
     → status 판정 → 캐시 저장 → ResearchContext 반환.

**실패 계약 (계약 §4):** 어떤 실패에도 경계 밖으로 예외를 던지지 않는다.
검색이 실패하거나 쓸 만한 결과가 없으면 status="failed" + 빈 findings를 반환한다.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.contracts import Finding, GoalDefinition, ResearchContext
from app.research import cache, gemini_client
from app.research.filters import passes_trust_filter, sanitize_metric
from app.research.query_builder import build_search_queries

logger = logging.getLogger(__name__)

MAX_FINDINGS = 8  # 계약 §4: 목표 3~8건
OK_THRESHOLD = 3  # 3건 이상이면 ok, 1~2건이면 partial, 0건이면 failed


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

        for query in queries:
            try:
                grounded = gemini_client.grounded_search(query)
                structured = gemini_client.structure_findings(
                    goal.goal_text, query, grounded.text, grounded.sources
                )
            except Exception:
                # 한 관점 실패는 전체 실패로 번지지 않는다 (다른 관점으로 partial 확보 가능)
                logger.exception("research query failed: %r", query)
                continue

            for item in structured:
                if item.source_index < 0 or item.source_index >= len(grounded.sources):
                    continue  # 모델이 범위 밖 인덱스를 낸 경우 방어
                src = grounded.sources[item.source_index]
                if not passes_trust_filter(src) or src.url in seen_urls:
                    continue
                seen_urls.add(src.url)
                collected.append(
                    Finding(
                        finding_id=f"F{len(collected) + 1}",
                        source_title=src.title,
                        source_url=src.url,
                        source_type=item.source_type,
                        published_date=None,  # grounding metadata에 신뢰할 발행일 없음 → null
                        summary=item.summary.strip(),
                        relevant_method=item.relevant_method.strip(),
                        metric_snippet=sanitize_metric(item.metric_snippet),
                    )
                )
                if len(collected) >= MAX_FINDINGS:
                    break
            if len(collected) >= MAX_FINDINGS:
                break

        if not collected:
            # 쓸 만한 근거 0건 → failed (계약: failed는 빈 findings). 캐싱하지 않음(재시도 허용)
            logger.warning("research produced no findings: goal_id=%s", goal_id)
            return _failed(goal_id, queries)

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
