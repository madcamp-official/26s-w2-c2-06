"""
파인튜닝 학습 데이터 품질 검수 — Gemini 자체 2차 채점.

generate_targets.py가 만든 (시나리오, DraftPlan, RoadmapResult)를 다시 Gemini에게 보여주고
"이 결과물이 실제 서비스에 나가도 될 품질인가"를 기준별로 채점시킨다. 기준 미달 샘플은
학습 데이터에서 제외한다 (keep=false).

실행: docker compose exec app python3 scripts/finetune/score_targets.py \
        --targets /tmp/targets_full.json --out /tmp/targets_scored.json
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
    fitness_quality: int = Field(description="1~5, 적합성 판정(Pivot/진행)이 타당하고 근거가 구체적인가")
    task_quality: int = Field(description="1~5, task가 추상적이지 않고 실제로 이번 주에 바로 시도할 수 있을 만큼 구체적인가")
    metric_quality: int = Field(description="1~5, 평가 지표(baseline/target)가 해당 task와 논리적으로 맞아떨어지는가")
    policy_compliance: int = Field(
        description="1~5, 쉬운 언어 사용/Layer3 최종판단 문구/전사도입 지양 등 정책을 잘 지켰는가"
    )
    has_empty_content: bool = Field(description="tasks나 fitness_assessment가 비어있어 사실상 내용이 없으면 true")
    keep: bool = Field(description="이 샘플을 학습 데이터로 채택해도 되면 true, 품질 미달이면 false")
    reason: str = Field(description="keep 판단의 핵심 이유 한 문장")


_SCORING_PROMPT_TEMPLATE = """
너는 AX(AI 전환) 로드맵 생성 결과물의 품질 검수자다. 아래는 팀 상황(goal_text, onboarding)과
그에 대해 생성된 로드맵 결과(roadmap_result)다. 이 결과물이 실제 중간관리자에게 그대로
전달돼도 괜찮은 품질인지 엄격하게 채점해라. 특히 task나 fitness_assessment가 비어있거나
(개수 0), 내용이 뻔하고 추상적이기만 하면 낮은 점수를 줘라. 각 기준 1~5점, 종합적으로
3점 미만이 하나라도 있으면 keep=false로 판단해라.

## 팀 상황
{context}

## 생성된 로드맵 결과
{roadmap_json}
"""


def score_one(client, context: str, roadmap_json: str) -> QualityScore:
    prompt = _SCORING_PROMPT_TEMPLATE.format(context=context, roadmap_json=roadmap_json)
    response = client.models.generate_content(
        model=settings.gemini_model,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=QualityScore,
        ),
    )
    if response.parsed is not None:
        return response.parsed
    return QualityScore.model_validate_json(response.text)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--targets", type=str, required=True)
    parser.add_argument("--out", type=str, required=True)
    parser.add_argument("--start", type=int, default=0)
    args = parser.parse_args()

    data = json.loads(Path(args.targets).read_text())
    results = data["results"]
    print(f"▶ {len(results)}개 채점 시작 ({args.start}번부터)")

    out_path = Path(args.out)
    scored = []
    if out_path.exists() and args.start > 0:
        scored = json.loads(out_path.read_text())["scored"]

    client = get_client()
    for i in range(args.start, len(results)):
        r = results[i]
        context = (
            f"goal_text: {r['goal']['goal_text']}\n"
            f"industry: {r['onboarding']['industry']}, team_size: {r['onboarding']['team_size']}\n"
            f"repetitive_tasks: {json.dumps(r['onboarding']['repetitive_tasks'], ensure_ascii=False)}"
        )
        roadmap_json = json.dumps(r["roadmap_result"], ensure_ascii=False)
        try:
            score = score_one(client, context, roadmap_json)
            scored.append({"idx": r["idx"], "score": score.model_dump(), "keep": score.keep})
            print(f"[{r['idx']}] 종합 keep={score.keep} (적합성{score.fitness_quality}/task{score.task_quality}/지표{score.metric_quality}/정책{score.policy_compliance}) - {score.reason[:60]}")
        except Exception as e:
            print(f"[{r['idx']}] 채점 실패: {type(e).__name__} {str(e)[:150]}")
            scored.append({"idx": r["idx"], "score": None, "keep": False})

        out_path.write_text(json.dumps({"scored": scored}, ensure_ascii=False, indent=2), encoding="utf-8")

    kept = sum(1 for s in scored if s["keep"])
    print(f"\n총 {len(scored)}개 채점, {kept}개 채택, {len(scored) - kept}개 제외")


if __name__ == "__main__":
    main()
