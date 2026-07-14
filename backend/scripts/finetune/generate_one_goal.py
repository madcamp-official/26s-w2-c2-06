"""
파인튜닝된 모델로 학습에 전혀 안 쓰인 시나리오 하나를 골라 목표+진단을 생성하고,
결과를 JSON 파일로 저장한다 (백엔드로 옮겨서 실제 파이프라인에 넣기 위함).

실행 (camp10의 finetune 컨테이너 안에서):
    python3 generate_one_goal.py --idx 100 --out /workspace/output/one_goal.json
"""

import argparse
import json
from pathlib import Path

from unsloth import FastLanguageModel
from peft import PeftModel

MODEL_NAME = "unsloth/Mistral-Small-24B-Instruct-2501-unsloth-bnb-4bit"
LORA_DIR = "/workspace/output/goal-model-lora"
SCENARIOS_PATH = "/workspace/scenarios_full.json"
MAX_SEQ_LENGTH = 4096

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
"""


def format_prompt(scenario: dict) -> str:
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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--idx", type=int, required=True)
    parser.add_argument("--out", type=str, required=True)
    args = parser.parse_args()

    scenarios = json.loads(Path(SCENARIOS_PATH).read_text())["scenarios"]
    scenario = scenarios[args.idx]
    prompt = format_prompt(scenario)

    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=MODEL_NAME, max_seq_length=MAX_SEQ_LENGTH, load_in_4bit=True, dtype=None
    )
    model = PeftModel.from_pretrained(model, LORA_DIR)
    FastLanguageModel.for_inference(model)

    messages = [{"role": "user", "content": prompt}]
    inputs = tokenizer.apply_chat_template(
        messages, tokenize=True, add_generation_prompt=True, return_tensors="pt"
    ).to(model.device)
    outputs = model.generate(input_ids=inputs, max_new_tokens=1024, temperature=0.3, do_sample=True)
    raw_text = tokenizer.decode(outputs[0][inputs.shape[1] :], skip_special_tokens=True)

    print("RAW OUTPUT:\n", raw_text)
    goal_output = json.loads(raw_text)

    result = {"idx": args.idx, "scenario": scenario, "goal_output": goal_output}
    Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n저장 완료: {args.out}")


if __name__ == "__main__":
    main()
