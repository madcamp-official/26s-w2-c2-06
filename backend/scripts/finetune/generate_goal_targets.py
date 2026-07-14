"""
기능 2 파인튜닝 데이터 생성 — "온보딩 인터뷰 결과 -> 5축 AX 성숙도 진단 + 목표 정의서".

generate_scenarios.py가 만든 150개 시나리오의 "온보딩 사실"(업종/인원/반복업무/팀원태그/
조직제약)만 입력으로 쓰고, goal_text는 다시 생성한다 (기존 scenario의 goal_text는 온보딩과
동시에 만들어진 것이라 "온보딩으로부터 도출"을 학습시키는 데 안 맞음 — 새로 생성해야 함).

실행: docker compose exec app python3 scripts/finetune/generate_goal_targets.py \
        --scenarios /tmp/scenarios_full.json --out /tmp/goal_targets_full.json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from google.genai import types

from app.roadmap.gemini_client import get_client
from app.core.config import settings
from goal_setting_schema import Goal2Output


_PROMPT_TEMPLATE = """
너는 AX(AI 전환) 코칭 서비스에서 "온보딩 인터뷰 결과를 보고 AX 성숙도를 진단하고 목표를
정의하는" 역할을 맡는다. 아래는 한 팀의 온보딩 인터뷰 결과다. 이것만 보고(추가 질문 없이)
5축 성숙도 진단과 목표 정의서 한 문장을 만들어라.

## 온보딩 인터뷰 결과
- 업종: {industry}
- 팀 인원: {team_size}명
- 허용 도구: {allowed_tools}
- 연동 시스템: {integrated_systems}
- 외부 AI 허용 여부: {external_ai_allowed}
- 보안 수준: {security_level}

반복 업무 목록:
{tasks_block}

팀원 태깅:
{members_block}

## 진단 지침
- strategy_clarity: 반복업무 목록은 있지만 "무엇을 바꿀지"에 대한 목표 문장이 아직 없다는 점을
  감안해서 판단해라 (목표가 이미 있다면 이 인터뷰에 없으므로 낮게 볼 것).
- tool_usage: allowed_tools가 비어 있거나 개인용 도구뿐이면 낮게, 팀 표준 도구/가이드라인이
  있으면 높게.
- team_readiness: member_tags의 ai_comfort_level 분포를 보고 판단 (편차가 크면 중간 이하).
- data_accessibility: repetitive_tasks의 current_method가 흩어진 수기/엑셀 위주면 낮게,
  이미 시스템(integrated_systems)에 있으면 높게.
- measurement_system: 온보딩 데이터 자체에 "소요시간"은 있지만 이걸 추적/측정하는 습관이
  드러나지 않으면 낮게 (기본적으로 낮게 잡는 것이 안전).
- goal_text: 반복업무 중 소요시간이 크고 빈도가 잦은 것 1~2개를 중심으로, "무엇의 반복 시간을
  줄여서 팀원이 어디에 더 시간을 쓰게 할지"를 구체적으로 담아 한 문장으로 써라. 추상적인 "AI를
  도입한다" 식 문장 금지.
"""


def format_scenario_as_onboarding_prompt(scenario: dict) -> str:
    tasks_block = "\n".join(
        f"- {t['title']} (빈도: {t['frequency']}, 정형여부: {'정형' if t['is_standardized'] else '비정형'}, "
        f"평균 소요시간: {t['avg_time_minutes']}분, 민감정보 포함: {t['contains_sensitive_info']}, "
        f"현재 처리방식: {t['current_method']})"
        for t in scenario["repetitive_tasks"]
    ) or "(없음)"
    members_block = "\n".join(
        f"- {m['member_id']}: 강점 {', '.join(m['strengths']) or '없음'}, "
        f"AI 활용 편안함 {m['ai_comfort_level']}, 업무부담 {m['workload_level']}"
        for m in scenario["member_tags"]
    ) or "(없음)"

    return _PROMPT_TEMPLATE.format(
        industry=scenario["industry"],
        team_size=scenario["team_size"],
        allowed_tools=", ".join(scenario["allowed_tools"]) or "없음",
        integrated_systems=", ".join(scenario["integrated_systems"]) or "없음",
        external_ai_allowed=scenario["external_ai_allowed"],
        security_level=scenario["security_level"],
        tasks_block=tasks_block,
        members_block=members_block,
    )


def generate_one(client, prompt: str, model: str) -> Goal2Output:
    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=Goal2Output,
        ),
    )
    if response.parsed is not None:
        return response.parsed
    return Goal2Output.model_validate_json(response.text)


DEFAULT_MODELS = [
    "gemini-3.1-flash-lite",
    "gemini-3.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.5-flash",
    "gemini-2.0-flash-lite",
    "gemini-2.0-flash",
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenarios", type=str, required=True)
    parser.add_argument("--out", type=str, required=True)
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument(
        "--models",
        type=str,
        default=",".join(DEFAULT_MODELS),
        help="쉼표로 구분된 모델 목록. 하나가 429(할당량 소진)면 다음 모델로 자동 전환",
    )
    args = parser.parse_args()
    models = args.models.split(",")

    scenarios = json.loads(Path(args.scenarios).read_text())["scenarios"]
    print(f"▶ 시나리오 {len(scenarios)}개 로드, {args.start}번부터 처리, 모델 순서: {models}")

    out_path = Path(args.out)
    results = []
    failures = []
    if out_path.exists() and args.start > 0:
        results = json.loads(out_path.read_text())["results"]

    client = get_client()
    model_idx = 0
    for idx in range(args.start, len(scenarios)):
        scenario = scenarios[idx]
        prompt = format_scenario_as_onboarding_prompt(scenario)
        t0 = time.time()

        while True:
            if model_idx >= len(models):
                print(f"[{idx}] 모든 모델 할당량 소진 — 중단")
                failures.append({"idx": idx, "error": "모든 모델 할당량 소진"})
                out_path.write_text(
                    json.dumps({"results": results, "failures": failures}, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                print(f"\n총 {len(results)}개 성공, {len(failures)}개 실패 (모델 소진으로 조기 종료)")
                return
            current_model = models[model_idx]
            try:
                output = generate_one(client, prompt, current_model)
                results.append(
                    {
                        "idx": idx,
                        "scenario": scenario,
                        "onboarding_prompt": prompt,
                        "goal_output": output.model_dump(),
                        "model": current_model,
                    }
                )
                elapsed = time.time() - t0
                print(f"[{idx}] 완료 ({elapsed:.1f}s, {current_model}) — goal: {output.goal_text[:60]}")
                break
            except Exception as e:
                msg = str(e)
                if "RESOURCE_EXHAUSTED" in msg or "429" in msg:
                    print(f"[{idx}] {current_model} 할당량 소진 — 다음 모델로 전환")
                    model_idx += 1
                    continue
                print(f"[{idx}] 실패({current_model}): {type(e).__name__} {msg[:200]}")
                failures.append({"idx": idx, "error": f"{type(e).__name__}: {e}", "model": current_model})
                break

        out_path.write_text(
            json.dumps({"results": results, "failures": failures}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    print(f"\n총 {len(results)}개 성공, {len(failures)}개 실패")


if __name__ == "__main__":
    main()
