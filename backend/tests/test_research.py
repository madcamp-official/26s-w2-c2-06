"""기능 3 `run_research()` 동작 검증 (계약 §7-3, §4 실패 계약, v0.4 소스 API 아키텍처).

출력 스키마 + 실패 경로 + 캐싱 + seed 병합 + url필터/중복제거.
네트워크를 타지 않도록 소스 어댑터(semantic_scholar/arxiv/github의 `search`)를 monkeypatch한다.
(공동 소유 스키마/픽스처 검증은 test_contracts.py, 실제 API 스모크는 scripts/smoke_research.py.)
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.contracts.goal import GoalDefinition, OrgConstraints
from app.contracts.research import Finding, ResearchContext
from app.research import cache, run_research
from app.research.service import MAX_FINDINGS, SEED_LIMIT
from app.research.sources import arxiv, github, semantic_scholar, tavily
from app.research.sources.base import RawSource

FIXTURES = Path(__file__).resolve().parent.parent / "app" / "fixtures"


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    yield
    cache.clear()


def _goal_001() -> GoalDefinition:
    """seed_findings_goal_001.json(2건)이 존재하는 목표."""
    return GoalDefinition.model_validate(json.loads((FIXTURES / "goal_001.json").read_text()))


def _goal(goal_id: str) -> GoalDefinition:
    """seed 파일이 없는 임의 목표 (seed 영향 배제용)."""
    return GoalDefinition(
        goal_id=goal_id,
        goal_text="테스트 목표",
        org_constraints=OrgConstraints(security_level="medium"),
    )


def _paper(url: str, title: str = "T", abstract: str | None = "A. B. C.") -> RawSource:
    return RawSource(title=title, url=url, abstract=abstract, source_type="research", published_date="2025")


def _install_sources(monkeypatch, *, ss=None, arx=None, gh=None, tv=None):
    """어댑터 search를 결정적 가짜로 교체. 호출 횟수를 센다. 값이 Exception이면 raise."""
    calls = {"n": 0}

    def make(ret):
        def _search(query, limit=4):
            calls["n"] += 1
            if isinstance(ret, Exception):
                raise ret
            return list(ret)
        return _search

    monkeypatch.setattr(semantic_scholar, "search", make(ss if ss is not None else []))
    monkeypatch.setattr(arxiv, "search", make(arx if arx is not None else []))
    monkeypatch.setattr(github, "search", make(gh if gh is not None else []))
    monkeypatch.setattr(tavily, "search", make(tv if tv is not None else []))
    return calls


def test_seed_fixture_becomes_valid_findings():
    data = json.loads((FIXTURES / "seed_findings_goal_001.json").read_text())
    assert len(data) >= 1
    for i, sd in enumerate(data, 1):
        Finding.model_validate({"finding_id": f"F{i}", **sd})  # id 부여 시 유효


def test_output_is_valid_context_and_ok(monkeypatch):
    _install_sources(monkeypatch, ss=[_paper("https://a/x"), _paper("https://b/y")], arx=[_paper("https://c/z")])
    ctx = run_research(_goal("goal_no_seed"))

    ResearchContext.model_validate(json.loads(ctx.model_dump_json()))  # 라운드트립
    assert ctx.status == "ok"  # 3건 이상
    assert [f.finding_id for f in ctx.findings] == ["F1", "F2", "F3"]
    assert ctx.search_queries
    assert all(f.source_url.startswith("http") for f in ctx.findings)


def test_partial_when_few(monkeypatch):
    _install_sources(monkeypatch, ss=[_paper("https://a/x")])
    ctx = run_research(_goal("goal_no_seed"))
    assert ctx.status == "partial" and len(ctx.findings) == 1


# ── 소스 다양성 (pillar 라운드로빈, v0.6) ───────────────────────


def test_practice_and_trend_not_crowded_out_by_research(monkeypatch):
    """semantic_scholar+arxiv(research pillar)만으로 MAX_FINDINGS를 다 채울 만큼 결과가 많아도,
    github(practice)·tavily(trend) 결과가 최종 findings에 반드시 섞여야 한다.
    (v0.5까지의 버그: 고정 어댑터 순서 `ss→arx→gh→tv` 때문에 research 두 개만으로
    MAX_FINDINGS가 차버리면 practice/trend는 같은 요청에서 한 번도 반영되지 못했다.)"""
    _install_sources(
        monkeypatch,
        ss=[_paper(f"https://ss/{i}") for i in range(4)],
        arx=[_paper(f"https://arx/{i}") for i in range(4)],
        gh=[RawSource(title="GH repo", url="https://github.com/x", abstract="A", source_type="practice", published_date=None)],
        tv=[RawSource(title="TV post", url="https://blog/x", abstract="A", source_type="trend", published_date=None)],
    )
    ctx = run_research(_goal("goal_no_seed"))

    assert len(ctx.findings) == MAX_FINDINGS  # 후보 10건 중 상한까지 채움
    types = {f.source_type for f in ctx.findings}
    assert "practice" in types, "GitHub(practice) 결과가 최종 findings에서 밀려났다"
    assert "trend" in types, "Tavily(trend) 결과가 최종 findings에서 밀려났다"


def test_pillar_roundrobin_picks_practice_and_trend_first_within_query(monkeypatch):
    """pillar 순서(practice→trend→research)대로 동률 시 실무 근거를 먼저 채택하는지 확인."""
    _install_sources(
        monkeypatch,
        ss=[_paper("https://ss/0")],
        arx=[_paper("https://arx/0")],
        gh=[RawSource(title="GH repo", url="https://github.com/x", abstract="A", source_type="practice", published_date=None)],
        tv=[RawSource(title="TV post", url="https://blog/x", abstract="A", source_type="trend", published_date=None)],
    )
    ctx = run_research(_goal("goal_no_seed"))
    # 라운드로빈 1라운드: practice, trend, research(ss), research(arx) 순
    assert [f.source_type for f in ctx.findings] == ["practice", "trend", "research", "research"]


# ── seed 병합 (계약 §2.6) ──────────────────────────────────────


def test_seed_findings_merged_first(monkeypatch):
    _install_sources(monkeypatch, ss=[_paper("https://a/x")])
    ctx = run_research(_goal_001())  # seed(SEED_LIMIT건, 실제 파일엔 더 많음) + 실시간 1
    assert ctx.status == "ok"
    assert len(ctx.findings) == SEED_LIMIT + 1
    seed_part, live_part = ctx.findings[:SEED_LIMIT], ctx.findings[SEED_LIMIT:]
    assert all(f.source_url.startswith("internal://") for f in seed_part)  # seed 먼저
    assert all(f.source_url.startswith("http") for f in live_part)  # 실시간 뒤
    # seed 파일에 실제 리포트에서 뽑은 수치 근거가 여럿 있어야 함 (SPEC 2.6 출처 있는 인용)
    data = json.loads((FIXTURES / "seed_findings_goal_001.json").read_text())
    assert any(sd.get("metric_snippet") for sd in data)


def test_seed_only_is_ok_when_reaches_threshold(monkeypatch):
    _install_sources(monkeypatch, ss=[], arx=[])  # 실시간 전부 무결과
    ctx = run_research(_goal_001())
    # SEED_LIMIT(4) >= OK_THRESHOLD(3) 이므로 seed만으로도 ok
    assert ctx.status == "ok" and len(ctx.findings) == SEED_LIMIT


# ── 실패 계약 ─────────────────────────────────────────────────


def test_failed_when_all_sources_fail_no_seed(monkeypatch):
    _install_sources(monkeypatch, ss=RuntimeError("down"), arx=RuntimeError("down"))
    ctx = run_research(_goal("goal_no_seed"))
    assert ctx.status == "failed" and ctx.findings == []


def test_failed_never_raises(monkeypatch):
    _install_sources(monkeypatch, ss=RuntimeError("boom"), arx=RuntimeError("boom"))
    ctx = run_research(_goal("goal_no_seed"))
    assert isinstance(ctx, ResearchContext) and ctx.status == "failed"


# ── 캐싱 (계약 §2.4) ──────────────────────────────────────────


def test_success_cached(monkeypatch):
    calls = _install_sources(monkeypatch, ss=[_paper("https://a/x"), _paper("https://b/y"), _paper("https://c/z")])
    first = run_research(_goal("goal_no_seed"))
    n_after = calls["n"]
    second = run_research(_goal("goal_no_seed"))
    assert first is second and calls["n"] == n_after  # 재조회 없음


def test_failed_not_cached(monkeypatch):
    _install_sources(monkeypatch, ss=RuntimeError("down"), arx=RuntimeError("down"))
    run_research(_goal("goal_no_seed"))
    assert cache.get("goal_no_seed") is None


# ── 방어: url 필터 / 중복 제거 ────────────────────────────────


def test_nonhttp_url_dropped(monkeypatch):
    _install_sources(monkeypatch, ss=[_paper("ftp://x/bad"), _paper("https://ok/1")])
    ctx = run_research(_goal("goal_no_seed"))
    assert [f.source_url for f in ctx.findings] == ["https://ok/1"]


def test_dedupe_by_url(monkeypatch):
    _install_sources(monkeypatch, ss=[_paper("https://dup/1"), _paper("https://dup/1")], arx=[_paper("https://dup/1")])
    ctx = run_research(_goal("goal_no_seed"))
    assert len(ctx.findings) == 1
