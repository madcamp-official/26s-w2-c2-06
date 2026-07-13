"""기능 3 계약 검증 테스트 (계약 §7-3, §4 실패 계약).

`run_research()` 출력이 `ResearchContext` 스키마를 만족하는지 + 실패 경로를 검증한다.
네트워크를 타지 않도록 Gemini 호출부(`grounded_search`/`structure_findings`)를 monkeypatch한다.
실제 API 스모크 테스트는 `scripts/smoke_research.py`(수동 실행)로 분리.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.contracts import GoalDefinition, ResearchContext
from app.research import cache, gemini_client, run_research
from app.research.gemini_client import GroundedResult, Source, StructuredFinding

FIXTURES = Path(__file__).resolve().parent.parent / "app" / "fixtures"


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def goal() -> GoalDefinition:
    return GoalDefinition.model_validate(json.loads((FIXTURES / "goal_001.json").read_text()))


def _install_fake(monkeypatch, sources, findings, *, raise_on_search=False):
    """grounded_search / structure_findings를 결정적 가짜로 교체. 호출 횟수를 센다."""
    calls = {"search": 0, "structure": 0}

    def fake_search(query: str) -> GroundedResult:
        calls["search"] += 1
        if raise_on_search:
            raise RuntimeError("검색 실패 시뮬레이션")
        return GroundedResult(text="요약", sources=list(sources))

    def fake_structure(goal_text, query, report_text, srcs) -> list[StructuredFinding]:
        calls["structure"] += 1
        return list(findings)

    monkeypatch.setattr(gemini_client, "grounded_search", fake_search)
    monkeypatch.setattr(gemini_client, "structure_findings", fake_structure)
    return calls


# ── 1. 픽스처 자체가 계약 스키마를 만족 ──────────────────────────────


def test_fixture_matches_schema():
    data = json.loads((FIXTURES / "research_context_goal_001.json").read_text())
    ctx = ResearchContext.model_validate(data)
    assert ctx.goal_id == "goal_001"
    assert ctx.status == "ok"
    assert [f.finding_id for f in ctx.findings] == ["F1", "F2", "F3"]


# ── 2. run_research 출력이 ResearchContext 스키마를 만족 (happy path) ──


def test_run_research_output_is_valid_context(monkeypatch, goal):
    sources = [
        Source(title="A", url="https://a.example/x"),
        Source(title="B", url="https://b.example/y"),
        Source(title="C", url="https://c.example/z"),
    ]
    findings = [
        StructuredFinding(source_index=0, source_type="practice", summary="s1", relevant_method="m1"),
        StructuredFinding(source_index=1, source_type="research", summary="s2", relevant_method="m2", metric_snippet="40% 감소"),
        StructuredFinding(source_index=2, source_type="trend", summary="s3", relevant_method="m3"),
    ]
    _install_fake(monkeypatch, sources, findings)

    ctx = run_research(goal)

    # 스키마 재검증 (직렬화 → 역직렬화 라운드트립)
    ResearchContext.model_validate(json.loads(ctx.model_dump_json()))
    assert ctx.goal_id == "goal_001"
    assert ctx.status == "ok"  # 3건 이상
    assert [f.finding_id for f in ctx.findings] == ["F1", "F2", "F3"]
    assert ctx.search_queries  # 쿼리 기록됨
    # 수치 있는 metric은 유지
    assert ctx.findings[1].metric_snippet == "40% 감소"


def test_partial_status_when_few_findings(monkeypatch, goal):
    sources = [Source(title="A", url="https://a.example/x")]
    findings = [StructuredFinding(source_index=0, source_type="trend", summary="s", relevant_method="m")]
    _install_fake(monkeypatch, sources, findings)

    ctx = run_research(goal)
    assert ctx.status == "partial"  # 1~2건
    assert len(ctx.findings) == 1


# ── 3. 실패 계약: 예외를 밖으로 던지지 않고 failed + 빈 findings ──────


def test_failed_contract_never_raises_on_exception(monkeypatch, goal):
    _install_fake(monkeypatch, [], [], raise_on_search=True)

    ctx = run_research(goal)  # 예외가 새어나오면 이 줄에서 실패
    assert isinstance(ctx, ResearchContext)
    assert ctx.status == "failed"
    assert ctx.findings == []
    assert ctx.goal_id == "goal_001"


def test_failed_when_no_usable_findings(monkeypatch, goal):
    # 소스는 있으나 구조화 결과가 비어 근거 0건 → failed
    _install_fake(monkeypatch, [Source(title="A", url="https://a.example/x")], [])
    ctx = run_research(goal)
    assert ctx.status == "failed"
    assert ctx.findings == []


# ── 4. 캐싱: 성공은 캐시, 실패는 캐시 안 함 (계약 §2.4) ───────────────


def test_success_is_cached(monkeypatch, goal):
    sources = [Source(title="A", url="https://a.example/x"), Source(title="B", url="https://b.example/y"), Source(title="C", url="https://c.example/z")]
    findings = [
        StructuredFinding(source_index=0, source_type="trend", summary="s1", relevant_method="m1"),
        StructuredFinding(source_index=1, source_type="trend", summary="s2", relevant_method="m2"),
        StructuredFinding(source_index=2, source_type="trend", summary="s3", relevant_method="m3"),
    ]
    calls = _install_fake(monkeypatch, sources, findings)

    first = run_research(goal)
    searches_after_first = calls["search"]
    second = run_research(goal)

    assert first is second  # 동일 객체 반환 (캐시 히트)
    assert calls["search"] == searches_after_first  # 재검색 없음


def test_failed_is_not_cached(monkeypatch, goal):
    _install_fake(monkeypatch, [], [], raise_on_search=True)
    run_research(goal)
    assert cache.get("goal_001") is None  # 실패는 캐싱하지 않음 → 재시도 가능


# ── 5. 방어 로직: 범위 밖 source_index / 수치 없는 metric ────────────


def test_out_of_range_source_index_is_dropped(monkeypatch, goal):
    sources = [Source(title="A", url="https://a.example/x")]
    findings = [
        StructuredFinding(source_index=5, source_type="trend", summary="bad", relevant_method="m"),  # 범위 밖 → drop
        StructuredFinding(source_index=0, source_type="trend", summary="ok", relevant_method="m"),
    ]
    _install_fake(monkeypatch, sources, findings)
    ctx = run_research(goal)
    # 유효한 1건만 남음 (partial), 잘못된 인덱스는 제외
    assert [f.summary for f in ctx.findings] == ["ok"]


def test_metric_without_number_is_nulled(monkeypatch, goal):
    sources = [Source(title="A", url="https://a.example/x")]
    findings = [
        StructuredFinding(source_index=0, source_type="trend", summary="s", relevant_method="m", metric_snippet="효과가 좋았다")
    ]
    _install_fake(monkeypatch, sources, findings)
    ctx = run_research(goal)
    assert ctx.findings[0].metric_snippet is None  # 숫자 없는 서술은 metric으로 인정 안 함
