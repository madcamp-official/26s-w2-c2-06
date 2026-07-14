"""
base 모델 vs 파인튜닝 후 모델 비교 — 학습에 전혀 쓰이지 않은(idx >= 90) 시나리오로 평가.

실행 (camp10의 finetune 컨테이너 안에서):
    python3 eval_goal_model.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from unsloth import FastLanguageModel
from peft import PeftModel

MODEL_NAME = "unsloth/Mistral-Small-24B-Instruct-2501-unsloth-bnb-4bit"
LORA_DIR = "/workspace/output/goal-model-lora"
SCENARIOS_PATH = "/workspace/scenarios_full.json"
MAX_SEQ_LENGTH = 4096

# generate_goal_targets.py의 프롬프트 포맷과 동일하게 맞춘다
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


def generate(model, tokenizer, prompt: str) -> str:
    FastLanguageModel.for_inference(model)
    messages = [{"role": "user", "content": prompt}]
    inputs = tokenizer.apply_chat_template(
        messages, tokenize=True, add_generation_prompt=True, return_tensors="pt"
    ).to(model.device)
    outputs = model.generate(input_ids=inputs, max_new_tokens=1024, temperature=0.3, do_sample=True)
    text = tokenizer.decode(outputs[0][inputs.shape[1] :], skip_special_tokens=True)
    return text


def main() -> None:
    scenarios = json.loads(Path(SCENARIOS_PATH).read_text())["scenarios"]
    test_scenarios = scenarios[90:93]  # 학습에 전혀 안 쓰인 시나리오 3개
    prompts = [format_prompt(s) for s in test_scenarios]

    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=MODEL_NAME,
        max_seq_length=MAX_SEQ_LENGTH,
        load_in_4bit=True,
        dtype=None,
    )

    print("\n########## BASE 모델 (파인튜닝 전) ##########")
    base_outputs = []
    for i, prompt in enumerate(prompts):
        print(f"\n--- [테스트 {i}] {test_scenarios[i]['industry']} / 인원 {test_scenarios[i]['team_size']} ---")
        out = generate(model, tokenizer, prompt)
        base_outputs.append(out)
        print(out[:800])

    print("\n\n########## 파인튜닝 후 (LoRA 적용) ##########")
    model = PeftModel.from_pretrained(model, LORA_DIR)
    ft_outputs = []
    for i, prompt in enumerate(prompts):
        print(f"\n--- [테스트 {i}] {test_scenarios[i]['industry']} / 인원 {test_scenarios[i]['team_size']} ---")
        out = generate(model, tokenizer, prompt)
        ft_outputs.append(out)
        print(out[:800])


if __name__ == "__main__":
    main()
