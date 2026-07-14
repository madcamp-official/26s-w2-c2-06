"""
기능 1(온보딩) · 기능 2(진단·목표) 데모 — Gemini 없이 FakeClient로 실행.

실제 Gemini 호출 없이 파이프라인을 눈으로 확인한다:
  ① build_onboarding: 확정 답변은 결정론적이라 애초에 LLM 불필요
  ② extract_task_candidates: 자유서술 → 후보 (여기만 LLM — FakeClient로 대체)
  ③ diagnose_and_set_goal: 5축 진단 + 목표 (LLM 판단 부분 — FakeClient로 대체)
  ④ 노션 블록 렌더링을 터미널에 텍스트로 출력

실행: cd backend && uv run python scripts/demo_feature12.py
"""

import json
import sys
from pathlib import Path

# 스크립트 직접 실행 시 backend 루트를 import 경로에 추가 (app·tests 패키지 인식용)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.contracts.maturity import AxisScore, Benchmark, MaturityAxis
from app.diagnosis import diagnose_and_set_goal
from app.diagnosis.draft import DiagnosisDraft
from app.notion.diagnosis_blocks import render_diagnosis_blocks
from app.onboarding import InterviewAnswers, build_onboarding, extract_task_candidates
from app.onboarding.extract import TaskCandidate, TaskCandidates
from tests.conftest import FakeClient

FIXTURES = Path(__file__).parent.parent / "app" / "fixtures"


def rule(title: str) -> None:
    print("\n" + "═" * 68)
    print(f"  {title}")
    print("═" * 68)


def block_to_text(block: dict) -> str:
    """노션 블록 JSON을 사람이 읽을 한 줄로 (데모 출력용)."""
    t = block["type"]
    payload = block[t]
    rich = "".join(rt.get("text", {}).get("content", "") for rt in payload.get("rich_text", []))
    icon = payload.get("icon", {}).get("emoji", "")
    prefix = {"heading_2": "▎", "callout": f"{icon} ", "quote": "❝ ", "bulleted_list_item": "• "}
    if t == "divider":
        return "  " + "─" * 40
    return "  " + prefix.get(t, "") + rich


# ─────────────────────────────────────────────────────────────────────────────
# ① 기능 1 — 확정 답변으로 OnboardingData 조립 (LLM 불필요)
# ─────────────────────────────────────────────────────────────────────────────
rule("① 기능 1 · 온보딩 인터뷰 → OnboardingData  (확정 답변 = 결정론적)")

answers = InterviewAnswers.model_validate(
    json.loads((FIXTURES / "interview_answers_marketing.json").read_text())
)
onboarding = build_onboarding(answers)  # client 안 넘겨도 됨 — 확정 답변이라 LLM 안 탐

print(f"업종: {onboarding.industry} · 팀 {onboarding.team_size}명 · "
      f"AI 활용수준: {onboarding.ai_adoption_level.value}")
env = onboarding.org_environment
print(f"조직환경: 가이드라인 {'있음' if env.has_ai_guideline else '없음'} · "
      f"지정도구 {env.designated_ai_tools or '없음'} · "
      f"외부AI {'허용' if env.external_ai_allowed else '제한'}")
print(f"\n반복 업무 {len(onboarding.repetitive_tasks)}건:")
for t in onboarding.repetitive_tasks:
    flag = "🔒민감" if t.contains_sensitive_info else "  "
    kind = "정형" if t.is_standardized else "비정형"
    print(f"  {flag} {t.title:22} | {t.frequency:8} | {kind} | {t.avg_time_minutes:.0f}분")


# ─────────────────────────────────────────────────────────────────────────────
# ② 기능 1 — 자유서술 → 후보 추출 (여기만 LLM. FakeClient로 대체)
# ─────────────────────────────────────────────────────────────────────────────
rule("② 기능 1 · 하루 자유서술 → 반복 업무 후보  (LLM 자리 = FakeClient)")

fake_extract = FakeClient(
    TaskCandidates(tasks=[
        TaskCandidate(title="SNS 카피 초안 작성", frequency="매일", is_standardized=False,
                      avg_time_minutes=30, current_method="직접 작성", needs_confirmation=True),
        TaskCandidate(title="주간 성과 리포트", frequency="주 1회 이상", is_standardized=True,
                      avg_time_minutes=120, contains_sensitive_info=True,
                      current_method="대시보드+엑셀", needs_confirmation=True),
    ])
)
narrative = "아침엔 SNS 카피를 쓰고, 금요일마다 대시보드 보고 주간 성과 리포트를 정리해요."
candidates = extract_task_candidates(fake_extract, narrative, onboarding.work_categories)
print(f'입력 서술: "{narrative}"\n')
for c in candidates:
    print(f"  · {c.title} (추정: {c.frequency}, "
          f"{'정형' if c.is_standardized else '비정형'}, {c.avg_time_minutes:.0f}분, "
          f"확인필요={c.needs_confirmation})")
print("\n→ 이 후보들을 프론트가 후속 5문항으로 사용자에게 확인받아 확정합니다.")


# ─────────────────────────────────────────────────────────────────────────────
# ③ 기능 2 — 진단 + 목표 (LLM 판단 자리 = FakeClient, 사실값은 온보딩에서)
# ─────────────────────────────────────────────────────────────────────────────
rule("③ 기능 2 · OnboardingData → 성숙도 진단 + 목표 정의서")

fake_diagnose = FakeClient(DiagnosisDraft(
    axis_scores=[
        AxisScore(axis=MaturityAxis.STRATEGY_CLARITY, score=2, interpretation="무엇을 바꿀지 목표 문장이 없음"),
        AxisScore(axis=MaturityAxis.TOOL_ADOPTION, score=2, interpretation="팀 표준 도구·프롬프트 없음"),
        AxisScore(axis=MaturityAxis.TEAM_READINESS, score=2, interpretation="팀원 간 활용 편차가 큼"),
        AxisScore(axis=MaturityAxis.DATA_ACCESS, score=3, interpretation="성과는 대시보드, 리뷰는 흩어져 있음"),
        AxisScore(axis=MaturityAxis.EVALUATION_SYSTEM, score=1, interpretation="시간 절감 지표 자체가 없음"),
    ],
    priority_axes=[MaturityAxis.EVALUATION_SYSTEM, MaturityAxis.STRATEGY_CLARITY, MaturityAxis.TOOL_ADOPTION],
    summary="관심은 있으나 실행 로드맵과 측정 지표가 없는 상태예요. 작은 업무 하나로 시작해 효과를 재보는 게 먼저예요.",
    benchmark=Benchmark(comment="국내 기업의 67.3%가 AX를 핵심 과제로 인식하지만 전사 내재화는 5.3%",
                        source="원티드 AX 인사이트 리포트, 2026"),
    goal_text="캠페인 성과 리포트와 카피 초안의 반복 시간을 줄여, 팀원이 전략·크리에이티브 판단에 더 집중하게 한다",
    integrated_systems=["대시보드"],
))
result = diagnose_and_set_goal(onboarding, goal_id="goal_marketing_001", client=fake_diagnose)

print(f"[성숙도 진단]  goal_id={result.maturity.goal_id}")
for s in result.maturity.axis_scores:
    bar = "■" * s.score + "□" * (5 - s.score)
    print(f"  {s.axis.value:8} {bar} {s.score}/5  — {s.interpretation}")
print(f"  우선순위: {' → '.join(a.value for a in result.maturity.priority_axes)}")

print(f"\n[목표 정의서]  goal_id={result.goal.goal_id}")
print(f"  목표: {result.goal.goal_text}")
oc = result.goal.org_constraints
print(f"  조직제약(결정론적): 허용도구={oc.allowed_tools or '없음'} · 연동={oc.integrated_systems} · "
      f"외부AI={'허용' if oc.external_ai_allowed else '제한'} · 보안={oc.security_level}")
print(f"  ↑ 보안 'high'인 이유: 민감정보 업무 있음 + 회사 가이드라인 없음 → 규칙상 최고 (4.4 게이트 유발)")


# ─────────────────────────────────────────────────────────────────────────────
# ④ 노션 렌더링 미리보기 (실제 발행 대신 블록을 텍스트로)
# ─────────────────────────────────────────────────────────────────────────────
rule("④ 노션 페이지 미리보기  (기능 2 블록 — 발행 없이 렌더링만)")

for block in render_diagnosis_blocks(result.maturity, result.goal):
    print(block_to_text(block))

print("\n✅ 데모 완료 — 실제 Gemini/Notion 호출 0건.")
