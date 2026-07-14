"""기능 2(AX 성숙도 진단 및 목표 설정) 동작 검증. Gemini는 FakeClient로 대체한다."""

import json
from pathlib import Path

from app.contracts.maturity import MATURITY_AXES, AxisScore, MaturityAxis, MaturityDiagnosis
from app.contracts.onboarding import (
    AiAdoptionLevel,
    OnboardingData,
    OrgEnvironment,
    RepetitiveTask,
)
from app.diagnosis import diagnose_and_set_goal
from app.diagnosis.draft import DiagnosisDraft
from app.diagnosis.service import _security_level
from tests.conftest import FakeClient

FIXTURES_DIR = Path(__file__).parent.parent / "app" / "fixtures"


def _load(name: str) -> dict:
    return json.loads((FIXTURES_DIR / name).read_text())


def _onboarding(**overrides) -> OnboardingData:
    base = dict(
        team_size=8,
        industry="커머스",
        ai_adoption_level=AiAdoptionLevel.OCCASIONAL,
        org_environment=OrgEnvironment(has_ai_guideline=False, external_ai_allowed=True),
        repetitive_tasks=[
            RepetitiveTask(
                title="주간 캠페인 성과 리포트",
                frequency="주 1회 이상",
                is_standardized=True,
                avg_time_minutes=120,
                contains_sensitive_info=True,
                current_method="대시보드 조회 후 엑셀 수기",
            )
        ],
    )
    base.update(overrides)
    return OnboardingData(**base)


def _draft_out_of_order() -> DiagnosisDraft:
    # 일부러 정규 순서와 다르게 넣어 정렬을 검증한다
    return DiagnosisDraft(
        axis_scores=[
            AxisScore(axis=MaturityAxis.EVALUATION_SYSTEM, score=1, interpretation="지표 없음"),
            AxisScore(axis=MaturityAxis.STRATEGY_CLARITY, score=2, interpretation="목표 문장 없음"),
            AxisScore(axis=MaturityAxis.TOOL_ADOPTION, score=2, interpretation="팀 표준 도구 없음"),
            AxisScore(axis=MaturityAxis.DATA_ACCESS, score=3, interpretation="일부 접근 가능"),
            AxisScore(axis=MaturityAxis.TEAM_READINESS, score=2, interpretation="편차 큼"),
        ],
        priority_axes=[MaturityAxis.EVALUATION_SYSTEM, MaturityAxis.STRATEGY_CLARITY],
        summary="실행 로드맵과 지표가 없는 상태",
        benchmark=None,
        goal_text="캠페인 리포트 반복 시간을 줄여 팀이 전략 판단에 더 집중하게 한다",
        integrated_systems=["대시보드"],
    )


def test_diagnose_orders_axes_and_propagates_goal_id():
    fake = FakeClient(_draft_out_of_order())
    result = diagnose_and_set_goal(_onboarding(), goal_id="goal_marketing_001", client=fake)

    # 성숙도 진단: 5개 축이 SPEC 4.2 정규 순서로 정렬된다
    assert [s.axis for s in result.maturity.axis_scores] == list(MATURITY_AXES)
    assert result.maturity.goal_id == "goal_marketing_001"
    # 목표 정의서와 진단이 같은 goal_id로 이어진다
    assert result.goal.goal_id == "goal_marketing_001"


def test_diagnose_maps_org_constraints_from_onboarding_not_llm():
    fake = FakeClient(_draft_out_of_order())
    onboarding = _onboarding(
        org_environment=OrgEnvironment(
            has_ai_guideline=False,
            designated_ai_tools=["Copilot"],
            external_ai_allowed=False,
        )
    )
    result = diagnose_and_set_goal(onboarding, client=fake)

    # 조직 제약은 온보딩 사실값에서 결정론적으로 채운다 (LLM이 지어내지 않음)
    assert result.goal.org_constraints.allowed_tools == ["Copilot"]
    assert result.goal.org_constraints.external_ai_allowed is False
    assert result.goal.org_constraints.integrated_systems == ["대시보드"]
    # 후보 업무는 온보딩 반복 업무 제목에서 그대로 가져온다
    assert result.goal.candidate_tasks_from_onboarding == ["주간 캠페인 성과 리포트"]


def test_security_level_rule():
    def make(sensitive: bool, guideline: bool) -> OnboardingData:
        return _onboarding(
            org_environment=OrgEnvironment(has_ai_guideline=guideline),
            repetitive_tasks=[
                RepetitiveTask(
                    title="t",
                    frequency="매일",
                    is_standardized=True,
                    avg_time_minutes=10,
                    contains_sensitive_info=sensitive,
                    current_method="수기",
                )
            ],
        )

    # 민감정보 + 가이드라인 없음 → high (4.4 게이트가 걸리도록)
    assert _security_level(make(sensitive=True, guideline=False)) == "high"
    assert _security_level(make(sensitive=True, guideline=True)) == "medium"
    assert _security_level(make(sensitive=False, guideline=False)) == "medium"
    assert _security_level(make(sensitive=False, guideline=True)) == "low"


def test_maturity_fixture_is_valid():
    diagnosis = MaturityDiagnosis.model_validate(_load("maturity_diagnosis_marketing.json"))
    assert len(diagnosis.axis_scores) == 5
    assert diagnosis.benchmark is not None
    assert diagnosis.benchmark.source  # 출처가 반드시 있어야 함 (SPEC 2.6)
