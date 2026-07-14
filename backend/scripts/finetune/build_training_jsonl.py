"""
기능 2(온보딩 -> 5축 진단 + 목표 정의서) 학습용 JSONL 조립.

- Gemini 2차 채점을 통과한(keep=true) 샘플은 그대로 포함
- 채점을 못 받은 샘플(할당량 소진으로 중단된 구간)은 규칙 기반 자동 검사만 통과하면 포함
  (스키마 완전성, goal_text 최소 길이, 뻔한 문구 아님)
- 학습 포맷: {"messages": [{"role": "user", "content": <온보딩 프롬프트>},
                          {"role": "assistant", "content": <goal_output JSON 문자열>}]}
  (OpenAI/대부분의 SFT 프레임워크가 받아들이는 표준 chat 포맷)

실행: docker compose exec app python3 scripts/finetune/build_training_jsonl.py \
        --targets /tmp/goal_targets_full.json --scored /tmp/goal_targets_scored.json \
        --out /tmp/training_data.jsonl
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

_GENERIC_PHRASES = ["AI를 도입한다", "AI를 활용한다", "업무를 개선한다"]


def rule_check(goal_output: dict) -> tuple[bool, str]:
    maturity = goal_output.get("maturity", {})
    axes = ["strategy_clarity", "tool_usage", "team_readiness", "data_accessibility", "measurement_system"]
    for axis in axes:
        axis_data = maturity.get(axis)
        if not axis_data or not isinstance(axis_data.get("score"), int):
            return False, f"{axis} 점수 누락"
        if not (1 <= axis_data["score"] <= 5):
            return False, f"{axis} 점수 범위 밖({axis_data['score']})"
        if not axis_data.get("interpretation") or len(axis_data["interpretation"]) < 5:
            return False, f"{axis} 해석 누락/짧음"

    goal_text = goal_output.get("goal_text", "")
    if len(goal_text) < 15:
        return False, "goal_text 너무 짧음"
    if goal_text.strip() in _GENERIC_PHRASES:
        return False, "goal_text가 뻔한 문구"

    return True, "규칙 통과"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--targets", type=str, required=True)
    parser.add_argument("--scored", type=str, required=True)
    parser.add_argument("--out", type=str, required=True)
    args = parser.parse_args()

    targets = json.loads(Path(args.targets).read_text())["results"]
    scored_data = json.loads(Path(args.scored).read_text())["scored"]
    scored_by_idx = {s["idx"]: s for s in scored_data}

    # idx 중복 제거 (혹시 겹치는 재실행 구간이 있었을 경우 나중 것 우선)
    targets_by_idx = {}
    for t in targets:
        targets_by_idx[t["idx"]] = t

    included = []
    excluded = []
    for idx, t in sorted(targets_by_idx.items()):
        goal_output = t["goal_output"]
        score_entry = scored_by_idx.get(idx)

        if score_entry is not None:
            if score_entry["keep"]:
                included.append((idx, t, "gemini_scored"))
            else:
                excluded.append((idx, "gemini_rejected"))
            continue

        ok, reason = rule_check(goal_output)
        if ok:
            included.append((idx, t, "rule_checked"))
        else:
            excluded.append((idx, f"rule_failed: {reason}"))

    out_path = Path(args.out)
    with out_path.open("w", encoding="utf-8") as f:
        for idx, t, source in included:
            example = {
                "messages": [
                    {"role": "user", "content": t["onboarding_prompt"]},
                    {"role": "assistant", "content": json.dumps(t["goal_output"], ensure_ascii=False)},
                ],
                "meta": {"idx": idx, "source": source},
            }
            f.write(json.dumps(example, ensure_ascii=False) + "\n")

    print(f"포함: {len(included)}개 (gemini_scored={sum(1 for *_ , s in included if s=='gemini_scored')}, "
          f"rule_checked={sum(1 for *_ , s in included if s=='rule_checked')})")
    print(f"제외: {len(excluded)}개")
    for idx, reason in excluded:
        print(f"  [{idx}] {reason}")
    print(f"저장: {out_path}")


if __name__ == "__main__":
    main()
