"""
diagnosis/service.py

기능 2 공개 진입점 (SPEC 4.2). 온보딩 결과 → ① 성숙도 진단(MaturityDiagnosis) + ② 목표 정의서
(GoalDefinition)를 만든다. ①은 노션 페이지에, ②는 기능 3·4의 입력으로 흘러간다.

판단이 필요한 부분만 Gemini로 만들고(축 점수·해석·목표 문장), 조직 제약(허용 도구·외부 AI·
보안 수준)은 온보딩 사실값에서 결정론적으로 채운다 — 조직 제약을 LLM이 지어내지 않게 한다(SPEC 2.6).
"""

import uuid

from google import genai
from pydantic import BaseModel

from app.contracts.goal import GoalDefinition, OrgConstraints
from app.contracts.maturity import MATURITY_AXES, MaturityDiagnosis
from app.contracts.onboarding import OnboardingData
from app.core.gemini import get_client, generate_structured
from app.diagnosis.draft import DiagnosisDraft
from app.diagnosis.prompts import build_diagnosis_prompt


class DiagnosisResult(BaseModel):
    """기능 2의 두 산출물 묶음. maturity는 노션 표시용, goal은 기능 3·4 입력용."""

    maturity: MaturityDiagnosis
    goal: GoalDefinition


def _security_level(onboarding: OnboardingData) -> str:
    """보안 수준을 온보딩 사실값에서 규칙 기반으로 정한다 (SPEC 4.4 게이트와 정합).

    민감정보를 다루는데 회사 가이드라인이 없으면 가장 높게 잡아 4.4 게이트가 걸리도록 한다.
    """
    has_sensitive = any(t.contains_sensitive_info for t in onboarding.repetitive_tasks)
    has_guideline = onboarding.org_environment.has_ai_guideline
    if has_sensitive and not has_guideline:
        return "high"
    if has_sensitive or not has_guideline:
        return "medium"
    return "low"


def _integrated_systems(onboarding: OnboardingData, draft: DiagnosisDraft) -> list[str]:
    """QA_amendments 1절 — 온보딩 조직 환경 질문("ERP나 데이터가 연결되어 있는지")에서 받은
    사실값을 목표 정의서의 조직 제약에 결정론적으로 반영한다(LLM이 지어내지 않게, SPEC 2.6과
    같은 원칙). 자유서술(반복 업무 현재 처리 방식)에서 LLM이 추가로 짚어낸 연동 시스템(예:
    task별 "대시보드" 언급)은 보조 신호로 계속 병합한다 — 온보딩 질문이 놓친 시스템까지 덮는다."""
    systems = list(draft.integrated_systems)
    if onboarding.org_environment.erp_data_integrated:
        for tool in onboarding.org_environment.designated_ai_tools or ["사내 AI 도구"]:
            if tool not in systems:
                systems.append(f"{tool} (ERP·사내 데이터 연동)")
    return systems


def _order_axis_scores(draft: DiagnosisDraft) -> DiagnosisDraft:
    """축 점수를 SPEC 4.2의 정규 순서로 정렬한다 (레이더 차트 축 순서 고정)."""
    by_axis = {s.axis: s for s in draft.axis_scores}
    ordered = [by_axis[axis] for axis in MATURITY_AXES if axis in by_axis]
    # 정규 축에 없는(중복/오분류) 항목이 있으면 뒤에 붙여 정보 손실을 막는다.
    ordered += [s for s in draft.axis_scores if s.axis not in MATURITY_AXES]
    return draft.model_copy(update={"axis_scores": ordered})


def diagnose_and_set_goal(
    onboarding: OnboardingData,
    goal_id: str | None = None,
    client: genai.Client | None = None,
) -> DiagnosisResult:
    gemini = client or get_client()
    draft = _order_axis_scores(
        generate_structured(gemini, build_diagnosis_prompt(onboarding), DiagnosisDraft)
    )

    resolved_goal_id = goal_id or f"goal_{uuid.uuid4().hex[:8]}"

    maturity = MaturityDiagnosis(
        goal_id=resolved_goal_id,
        axis_scores=draft.axis_scores,
        priority_axes=draft.priority_axes,
        summary=draft.summary,
        benchmark=draft.benchmark,
    )

    env = onboarding.org_environment
    goal = GoalDefinition(
        goal_id=resolved_goal_id,
        goal_text=draft.goal_text,
        org_constraints=OrgConstraints(
            allowed_tools=env.designated_ai_tools,
            integrated_systems=_integrated_systems(onboarding, draft),
            external_ai_allowed=env.external_ai_allowed,
            security_level=_security_level(onboarding),
        ),
        candidate_tasks_from_onboarding=[t.title for t in onboarding.repetitive_tasks],
    )

    return DiagnosisResult(maturity=maturity, goal=goal)
