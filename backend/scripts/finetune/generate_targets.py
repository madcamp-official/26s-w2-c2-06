"""
파인튜닝 학습 데이터의 "정답" 쪽 — 합성 시나리오마다 실제 프로덕션 파이프라인
(run_research -> run_stage_a -> run_stage_b, 전부 실제 Gemini 호출)을 태워
DraftPlan/RoadmapResult를 생성한다.

generate_scenarios.py가 만든 시나리오 파일을 입력으로 받는다. 시나리오 하나 실패해도
전체가 죽지 않도록 개별 try/except로 감싸고, 실패 목록은 별도로 기록한다.

실행: docker compose exec app python3 scripts/finetune/generate_targets.py \
        --scenarios /tmp/scenarios_full.json --out /tmp/targets_full.json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from app.contracts.goal import GoalDefinition, OrgConstraints
from app.contracts.onboarding import OnboardingData, RepetitiveTask, TeamMemberTag
from app.research import run_research
from app.roadmap.gemini_client import get_client
from app.roadmap.prompts import build_stage_a_prompt, build_stage_b_prompt
from app.roadmap.stage_a import run_stage_a
from app.roadmap.stage_b import run_stage_b


def build_goal_and_onboarding(idx: int, scenario: dict) -> tuple[GoalDefinition, OnboardingData]:
    goal = GoalDefinition(
        goal_id=f"synth_{idx:04d}",
        goal_text=scenario["goal_text"],
        org_constraints=OrgConstraints(
            allowed_tools=scenario["allowed_tools"],
            integrated_systems=scenario["integrated_systems"],
            external_ai_allowed=scenario["external_ai_allowed"],
            security_level=scenario["security_level"],
        ),
    )
    onboarding = OnboardingData(
        team_size=scenario["team_size"],
        industry=scenario["industry"],
        repetitive_tasks=[RepetitiveTask(**t) for t in scenario["repetitive_tasks"]],
        member_tags=[TeamMemberTag(**m) for m in scenario["member_tags"]],
    )
    return goal, onboarding


def process_one(idx: int, scenario: dict) -> dict:
    goal, onboarding = build_goal_and_onboarding(idx, scenario)
    research = run_research(goal)

    client = get_client()
    stage_a_prompt = build_stage_a_prompt(goal, research, onboarding)
    draft = run_stage_a(client, goal, research, onboarding)

    stage_b_prompt = build_stage_b_prompt(draft, goal)
    result = run_stage_b(client, draft, goal, research.status)

    return {
        "idx": idx,
        "goal": goal.model_dump(mode="json"),
        "onboarding": onboarding.model_dump(mode="json"),
        "research_status": research.status.value,
        "stage_a_prompt": stage_a_prompt,
        "draft_plan": draft.model_dump(mode="json"),
        "stage_b_prompt": stage_b_prompt,
        "roadmap_result": result.model_dump(mode="json"),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenarios", type=str, required=True)
    parser.add_argument("--out", type=str, required=True)
    parser.add_argument("--start", type=int, default=0, help="이어서 실행할 시작 인덱스")
    args = parser.parse_args()

    scenarios = json.loads(Path(args.scenarios).read_text())["scenarios"]
    print(f"▶ 시나리오 {len(scenarios)}개 로드, {args.start}번부터 처리")

    out_path = Path(args.out)
    results = []
    failures = []
    if out_path.exists() and args.start > 0:
        results = json.loads(out_path.read_text())["results"]

    for idx in range(args.start, len(scenarios)):
        scenario = scenarios[idx]
        t0 = time.time()
        try:
            r = process_one(idx, scenario)
            results.append(r)
            elapsed = time.time() - t0
            n_tasks = len(r["roadmap_result"]["tasks"])
            print(f"[{idx}] 완료 ({elapsed:.1f}s) — research={r['research_status']}, tasks={n_tasks}")
        except Exception as e:
            print(f"[{idx}] 실패: {type(e).__name__} {str(e)[:200]}")
            failures.append({"idx": idx, "error": f"{type(e).__name__}: {e}"})

        # 중간 저장 (긴 배치 도중 끊겨도 이어서 할 수 있도록)
        out_path.write_text(
            json.dumps({"results": results, "failures": failures}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    print(f"\n총 {len(results)}개 성공, {len(failures)}개 실패")
    if failures:
        print("실패 인덱스:", [f["idx"] for f in failures])


if __name__ == "__main__":
    main()
