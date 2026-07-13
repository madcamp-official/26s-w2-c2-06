"""기능 3 `run_research()` 동작 검증 (계약 §7-3, §4 실패 계약, v0.4 소스 API 아키텍처).

출력 스키마 + 실패 경로 + 캐싱 + seed 병합 + url필터/중복제거.
네트워크를 타지 않도록 소스 어댑터(`semantic_scholar.search`/`arxiv.search`)를 monkeypatch한다.
(공동 소유 스키마/픽스처 검증은 test_contracts.py, 실제 API 스모크는 scripts/smoke_research.py.)
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.contracts.goal import GoalDefinition, OrgConstraints
from app.contracts.research import Finding, ResearchContext
from app.research import cache, run_research
from app.research.sources import arxiv, semantic_scholar
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


def _install_sources(monkeypatch, *, ss=None, arx=None):
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


# ── seed 병합 (계약 §2.6) ──────────────────────────────────────


def test_seed_findings_merged_first(monkeypatch):
    _install_sources(monkeypatch, ss=[_paper("https://a/x")])
    ctx = run_research(_goal_001())  # seed 2 + 실시간 1 = 3
    assert ctx.status == "ok"
    assert ctx.findings[0].source_url.startswith("internal://")  # seed 먼저
    assert ctx.findings[-1].source_url.startswith("http")  # 실시간 뒤
    assert any(f.metric_snippet and "45%" in f.metric_snippet for f in ctx.findings)


def test_seed_only_is_partial(monkeypatch):
    _install_sources(monkeypatch, ss=[], arx=[])
    ctx = run_research(_goal_001())
    assert ctx.status == "partial" and len(ctx.findings) == 2


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
