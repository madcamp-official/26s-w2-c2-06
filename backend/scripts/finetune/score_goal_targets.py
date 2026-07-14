"""
기능 2 파인튜닝 데이터 품질 검수 — Gemini 자체 2차 채점.

generate_goal_targets.py 결과(온보딩 -> 5축 진단 + 목표 문장)를 다시 Gemini에게 보여주고
품질을 채점시킨다. 점수 미달 샘플은 keep=false로 표시해 학습 데이터에서 제외한다.

실행: docker compose exec app python3 scripts/finetune/score_goal_targets.py \
        --targets /tmp/goal_targets_full.json --out /tmp/goal_targets_scored.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from google.genai import types
from pydantic import BaseModel, Field

from app.roadmap.gemini_client import get_client
from app.core.config import settings


class QualityScore(BaseModel):
    diagnosis_grounding: int = Field(description="1~5, 5축 점수 각각이 온보딩 데이터의 구체적 근거에 기반했는가(뭉뚱그린 채점이면 낮게)")
    goal_specificity: int = Field(description="1~5, 목표 문장이 구체적이고 측정 가능하며 실행 가능한가 (추상적인 'AI를 도입한다'류면 낮게)")
    internal_consistency: int = Field(description="1~5, 5축 점수와 목표 문장이 서로 앞뒤가 맞는가 (예: 도구활용도가 낮다면서 고도화된 도구 활용을 전제한 목표는 모순)")
    keep: bool = Field(description="학습 데이터로 채택해도 되면 true")
    reason: str = Field(description="keep 판단 핵심 이유 한 문장")


_PROMPT_TEMPLATE = """
너는 AX 성숙도 진단 결과물의 품질 검수자다. 아래 온보딩 인터뷰 요약과, 그에 대해 생성된
5축 진단+목표 문장을 엄격하게 채점해라. 특히 점수의 근거가 구체적인지, 목표 문장이
막연하지 않은지를 중점적으로 봐라.

## 온보딩 인터뷰 요약
{onboarding_prompt}

## 생성된 결과
{goal_output_json}
"""


def score_one(client, onboarding_prompt: str, goal_output_json: str, model: str) -> QualityScore:
    prompt = _PROMPT_TEMPLATE.format(onboarding_prompt=onboarding_prompt, goal_output_json=goal_output_json)
    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=QualityScore,
        ),
    )
    if response.parsed is not None:
        return response.parsed
    return QualityScore.model_validate_json(response.text)


DEFAULT_MODELS = [
    "gemini-3.1-flash-lite",
    "gemini-flash-lite-latest",
    "gemini-3.5-flash",
    "gemini-2.0-flash-lite",
    "gemini-2.0-flash",
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--targets", type=str, required=True)
    parser.add_argument("--out", type=str, required=True)
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--models", type=str, default=",".join(DEFAULT_MODELS))
    args = parser.parse_args()
    models = args.models.split(",")

    data = json.loads(Path(args.targets).read_text())
    results = data["results"]
    print(f"▶ {len(results)}개 채점 시작 ({args.start}번부터), 모델 순서: {models}")

    out_path = Path(args.out)
    scored = []
    if out_path.exists() and args.start > 0:
        scored = json.loads(out_path.read_text())["scored"]

    client = get_client()
    model_idx = 0
    for i in range(args.start, len(results)):
        r = results[i]
        goal_output_json = json.dumps(r["goal_output"], ensure_ascii=False)

        while True:
            if model_idx >= len(models):
                print(f"[{r['idx']}] 모든 모델 할당량 소진 — 중단")
                out_path.write_text(json.dumps({"scored": scored}, ensure_ascii=False, indent=2), encoding="utf-8")
                kept = sum(1 for s in scored if s["keep"])
                print(f"\n총 {len(scored)}개 채점, {kept}개 채택 (모델 소진으로 조기 종료)")
                return
            current_model = models[model_idx]
            try:
                score = score_one(client, r["onboarding_prompt"], goal_output_json, current_model)
                scored.append({"idx": r["idx"], "score": score.model_dump(), "keep": score.keep})
                print(
                    f"[{r['idx']}] keep={score.keep} ({current_model}) "
                    f"(근거{score.diagnosis_grounding}/구체성{score.goal_specificity}/일관성{score.internal_consistency}) "
                    f"- {score.reason[:60]}"
                )
                break
            except Exception as e:
                msg = str(e)
                if "RESOURCE_EXHAUSTED" in msg or "429" in msg:
                    print(f"[{r['idx']}] {current_model} 할당량 소진 — 다음 모델로 전환")
                    model_idx += 1
                    continue
                print(f"[{r['idx']}] 채점 실패({current_model}): {type(e).__name__} {msg[:150]}")
                scored.append({"idx": r["idx"], "score": None, "keep": False})
                break

        out_path.write_text(json.dumps({"scored": scored}, ensure_ascii=False, indent=2), encoding="utf-8")

    kept = sum(1 for s in scored if s["keep"])
    print(f"\n총 {len(scored)}개 채점, {kept}개 채택, {len(scored) - kept}개 제외")


if __name__ == "__main__":
    main()
