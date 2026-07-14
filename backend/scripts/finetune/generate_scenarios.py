"""
파인튜닝 학습 데이터의 "입력" 쪽 — 합성 시나리오(GoalDefinition + OnboardingData) 생성.

Gemini에게 다양한 회사 프로필(업종/인원수/ERP연동/보안수준/반복업무/팀원태그)을 배치로
생성시킨다. 한 번 호출로 여러 개를 받아 호출 수를 줄이고, "서로 겹치지 않게"를 프롬프트에
명시해 다양성을 확보한다.

실행: docker compose exec app python3 scripts/finetune/generate_scenarios.py --count 5 --out /tmp/scenarios_sample.json
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


class GeneratedTask(BaseModel):
    title: str
    frequency: str = Field(description="예: '주 1회 이상' 또는 '월 1회 이하' 형식 그대로")
    is_standardized: bool
    avg_time_minutes: float = Field(description="0보다 큰 값, 1회 처리에 걸리는 평균 소요 시간(분)")
    contains_sensitive_info: bool
    current_method: str


class GeneratedMember(BaseModel):
    member_id: str = Field(description="익명 식별자, 예: member_a. 실명 금지")
    strengths: list[str]
    ai_comfort_level: str = Field(description="낮음/중간/높음 중 하나")
    workload_level: str = Field(description="낮음/중간/높음 중 하나")


class GeneratedScenario(BaseModel):
    industry: str
    team_size: int = Field(description="1 이상의 정수, 팀 인원 수")
    goal_text: str = Field(description="이 팀이 AX로 이루고 싶은 목표 문장 (기능2 산출물 스타일)")
    allowed_tools: list[str] = Field(description="예: ['Copilot'], ['ChatGPT Enterprise'], [] 등")
    integrated_systems: list[str] = Field(description="예: ['SAP'], ['자체 ERP'], [] 등")
    external_ai_allowed: bool
    security_level: str = Field(description="low/medium/high 중 하나")
    repetitive_tasks: list[GeneratedTask] = Field(description="2~5개")
    member_tags: list[GeneratedMember] = Field(description="2~6개")


class GeneratedScenarioBatch(BaseModel):
    scenarios: list[GeneratedScenario]


_PROMPT_TEMPLATE = """
너는 AX(AI 전환) 코칭 서비스를 위한 학습 데이터 생성기다. 서로 완전히 다른 {count}개의
가상 회사/팀 시나리오를 만들어라. 실제로 있을 법한 한국 중소/중견기업 팀 단위로 상상하고,
아래 다양성 축을 최대한 겹치지 않게 조합해라 (같은 조합 반복 금지):
{avoid_block}

- 업종: 제조업, 이커머스, 금융/보험, 헬스케어, 교육, 물류/유통, 미디어/콘텐츠, 공공기관,
  SaaS/IT 스타트업, 요식업 프랜차이즈 등에서 다양하게 선택
- 팀 인원: 3~50명 사이 다양하게
- ERP/사내시스템 연동 여부: SAP 같은 대형 ERP / 자체 구축 시스템 / 연동 시스템 없음(엑셀 위주)
  을 골고루 섞어라
- 보안 수준(security_level)과 외부 AI 허용 여부(external_ai_allowed): high+false,
  low+true 등 다양한 조합이 나오게 해라 — 특히 "보안은 높은데 외부 AI는 막혀있음" 같은
  까다로운 케이스도 몇 개 포함해라
- 반복 업무(repetitive_tasks)의 빈도(frequency)/정형성(is_standardized) 조합이
  "자주+정형", "자주+비정형", "가끔+정형", "가끔+비정형" 네 가지가 시나리오 전체에서
  고르게 나오도록 해라. 민감정보 포함(contains_sensitive_info=true) 업무도 일부 포함해라
- 팀원 태그(member_tags)의 ai_comfort_level/workload_level도 낮음/중간/높음 골고루

각 시나리오는 실제 온보딩 인터뷰에서 나올 법한 구체적인 디테일(회사가 뭘 하는 곳인지,
하루 일과 중 어떤 업무가 반복되는지, 사내 가이드가 있는지 없는지)을 goal_text와
repetitive_tasks.current_method에 자연스럽게 녹여라. 추상적으로 쓰지 말고 구체적으로.
"""


def generate_batch(count: int, avoid_industries: list[str]) -> GeneratedScenarioBatch:
    client = get_client()
    avoid_block = ""
    if avoid_industries:
        avoid_block = (
            "\n이미 다른 배치에서 아래 업종들을 충분히 다뤘으니 이번 배치는 되도록 "
            f"다른 업종 위주로 만들어라: {', '.join(avoid_industries)}\n"
        )
    prompt = _PROMPT_TEMPLATE.format(count=count, avoid_block=avoid_block)
    response = client.models.generate_content(
        model=settings.gemini_model,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=GeneratedScenarioBatch,
        ),
    )
    if response.parsed is not None:
        return response.parsed
    return GeneratedScenarioBatch.model_validate_json(response.text)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--total", type=int, default=5, help="총 목표 개수")
    parser.add_argument("--batch-size", type=int, default=10)
    parser.add_argument("--out", type=str, default="/tmp/scenarios_sample.json")
    args = parser.parse_args()

    all_scenarios: list[GeneratedScenario] = []
    seen_industries: list[str] = []
    batch_num = 0
    while len(all_scenarios) < args.total:
        remaining = args.total - len(all_scenarios)
        count = min(args.batch_size, remaining)
        batch_num += 1
        print(f"▶ 배치 {batch_num}: 시나리오 {count}개 생성 중... (누적 {len(all_scenarios)}/{args.total})")
        try:
            batch = generate_batch(count, seen_industries[-20:])
        except Exception as e:
            print(f"  배치 {batch_num} 실패, 스킵: {type(e).__name__} {str(e)[:200]}")
            continue
        all_scenarios.extend(batch.scenarios)
        seen_industries.extend(s.industry for s in batch.scenarios)
        print(f"  배치 완료: {len(batch.scenarios)}개 (누적 {len(all_scenarios)})")

    out_path = Path(args.out)
    out_path.write_text(
        json.dumps({"scenarios": [s.model_dump() for s in all_scenarios]}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\n총 {len(all_scenarios)}개 저장: {out_path}")

    from collections import Counter
    print("업종 분포:", dict(Counter(s.industry for s in all_scenarios)))
    print("보안수준 분포:", dict(Counter(s.security_level for s in all_scenarios)))
    print("외부AI허용 분포:", dict(Counter(s.external_ai_allowed for s in all_scenarios)))


if __name__ == "__main__":
    main()
