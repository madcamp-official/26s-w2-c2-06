"""수동 스모크 테스트 — 실제 Gemini grounding으로 run_research(goal_001) 1회 호출.

CI 자동 테스트(tests/test_contracts.py)는 네트워크를 타지 않는다. 이 스크립트는
실제 API 키/그라운딩이 동작하는지 사람이 눈으로 확인할 때만 수동 실행한다.

    cd backend && uv run python scripts/smoke_research.py

`GEMINI_API_KEY_RESEARCH`가 .env에 설정돼 있어야 하며, 무료 티어 RPD를 소모한다.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# 스크립트 직접 실행 시 backend 루트를 import 경로에 추가 (app 패키지 인식용)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv()  # .env → 환경변수 (settings가 읽음)

from app.contracts import GoalDefinition, ResearchContext  # noqa: E402
from app.research import cache, run_research  # noqa: E402

FIXTURES = Path(__file__).resolve().parent.parent / "app" / "fixtures"


def main() -> None:
    goal = GoalDefinition.model_validate(json.loads((FIXTURES / "goal_001.json").read_text()))
    print(f"▶ run_research(goal_id={goal.goal_id}) — 실제 grounding 호출...\n")

    cache.clear()
    ctx = run_research(goal)

    # 1) 스키마가 계약과 같은 형태인지 (라운드트립 재검증)
    ResearchContext.model_validate(json.loads(ctx.model_dump_json()))

    print(f"status        : {ctx.status}")
    print(f"goal_id       : {ctx.goal_id}")
    print(f"retrieved_at  : {ctx.retrieved_at.isoformat()}")
    print(f"search_queries: {len(ctx.search_queries)}개")
    for q in ctx.search_queries:
        print(f"   - {q}")
    print(f"findings      : {len(ctx.findings)}건\n")
    for f in ctx.findings:
        metric = f" | metric={f.metric_snippet!r}" if f.metric_snippet else ""
        print(f"  [{f.finding_id}] ({f.source_type}) {f.source_title}{metric}")
        print(f"        url   : {f.source_url}")
        print(f"        method: {f.relevant_method}")
        print(f"        summary: {f.summary}\n")

    # 2) 캐시 검증: 재호출 시 동일 객체 (재검색 없음)
    if ctx.status != "failed":
        again = run_research(goal)
        print(f"cache hit(재호출 동일객체): {again is ctx}")

    print("\n✅ 스키마 검증 통과 (픽스처와 동일한 ResearchContext 형태)")


if __name__ == "__main__":
    main()
