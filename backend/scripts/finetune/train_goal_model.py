"""
기능 2(온보딩 -> 5축 진단 + 목표 정의서) QLoRA 파인튜닝.

베이스 모델: mistralai/Mistral-Small-24B-Instruct-2501 (4bit 로드, unsloth로 VRAM 절약)
데이터: /workspace/training_data.jsonl (messages 포맷, build_training_jsonl.py 산출물)

실행 (camp10의 finetune 컨테이너 안에서):
    python3 train_goal_model.py
"""

from datasets import load_dataset, disable_caching
from trl import SFTTrainer, SFTConfig
from unsloth import FastLanguageModel

# trl의 SFTTrainer._prepare_dataset()이 내부적으로 dataset.map()을 호출하면서 캐시 지문 계산을
# 위해 처리 함수를 dill로 pickle하려 하는데, unsloth가 패치한 tokenizer 내부 객체가 pickle이
# 안 돼서 실패한다. 캐싱을 꺼서 지문 계산(pickle) 자체를 건너뛴다.
disable_caching()

MODEL_NAME = "unsloth/Mistral-Small-24B-Instruct-2501-unsloth-bnb-4bit"
DATA_PATH = "/workspace/training_data.jsonl"
OUTPUT_DIR = "/workspace/output/goal-model-lora"
MAX_SEQ_LENGTH = 4096


def main() -> None:
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=MODEL_NAME,
        max_seq_length=MAX_SEQ_LENGTH,
        load_in_4bit=True,
        dtype=None,
    )

    model = FastLanguageModel.get_peft_model(
        model,
        r=16,
        lora_alpha=32,
        lora_dropout=0.05,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        bias="none",
        use_gradient_checkpointing="unsloth",
        random_state=42,
    )
    FastLanguageModel.for_training(model)

    dataset = load_dataset("json", data_files=DATA_PATH, split="train")

    # trl의 SFTTrainer._prepare_dataset()은 "input_ids" 컬럼이 이미 있으면(is_processed=True)
    # 내부 map() 호출(포맷팅/청크화)을 전부 건너뛴다. dataset.map()에 클로저를 넘기면 datasets가
    # 캐시 지문 계산을 위해 함수를 dill로 pickle하려다 unsloth가 패치한 tokenizer 내부 객체
    # 때문에 실패하므로, map()을 아예 안 타도록 우리가 직접 토크나이징해서 input_ids까지 만든다.
    texts, input_ids_list, attention_mask_list = [], [], []
    for ex in dataset:
        text = tokenizer.apply_chat_template(ex["messages"], tokenize=False, add_generation_prompt=False)
        enc = tokenizer(text, truncation=True, max_length=MAX_SEQ_LENGTH)
        texts.append(text)
        input_ids_list.append(enc["input_ids"])
        attention_mask_list.append(enc["attention_mask"])

    dataset = dataset.add_column("text", texts)
    dataset = dataset.add_column("input_ids", input_ids_list)
    dataset = dataset.add_column("attention_mask", attention_mask_list)
    print(f"학습 샘플 {len(dataset)}개, 예시 하나:\n{dataset[0]['text'][:500]}")

    trainer = SFTTrainer(
        model=model,
        processing_class=tokenizer,
        train_dataset=dataset,
        args=SFTConfig(
            output_dir=OUTPUT_DIR,
            dataset_num_proc=1,
            dataset_text_field="text",
            max_length=MAX_SEQ_LENGTH,
            per_device_train_batch_size=2,
            gradient_accumulation_steps=4,
            num_train_epochs=3,
            learning_rate=2e-4,
            logging_steps=1,
            save_strategy="epoch",
            optim="adamw_8bit",
            warmup_ratio=0.05,
            lr_scheduler_type="cosine",
            report_to="none",
        ),
    )

    trainer.train()
    model.save_pretrained(OUTPUT_DIR)
    tokenizer.save_pretrained(OUTPUT_DIR)
    print(f"LoRA 어댑터 저장 완료: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
