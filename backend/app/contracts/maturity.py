"""
contracts/maturity.py

2번(AX 성숙도 진단 및 목표 설정)의 산출물 중 **성숙도 진단** 스키마 (SPEC.md 4.2).
목표 정의서(GoalDefinition, goal.py)와 함께 기능 2가 내보내는 두 산출물 중 하나이며,
이쪽은 기능 3·4의 결과물과 함께 **노션 페이지에 표시**된다 (레이더 차트 + 축별 우선순위).

- 5개 축: 전략 명확성 / 도구 활용도 / 팀 수용력 / 데이터 접근성 / 평가 체계 (SPEC 4.2 고정)
- 축별 1~5점 + 해석 코멘트 + (선택) 출처 있는 벤치마크 코멘트 (SPEC 2.6 — 출처 있을 때만)

공동 소유 — 변경 시 SPRINT1_CONTRACT.md 8절 절차를 따른다. 생성 로직은 app/diagnosis/ 소유.
"""

from enum import Enum

from pydantic import BaseModel, Field


class MaturityAxis(str, Enum):
    STRATEGY_CLARITY = "전략 명확성"
    TOOL_ADOPTION = "도구 활용도"
    TEAM_READINESS = "팀 수용력"
    DATA_ACCESS = "데이터 접근성"
    EVALUATION_SYSTEM = "평가 체계"


# SPEC 4.2에 고정된 5개 축의 정규 순서 (레이더 차트 축 순서·검증에 사용)
MATURITY_AXES: tuple[MaturityAxis, ...] = (
    MaturityAxis.STRATEGY_CLARITY,
    MaturityAxis.TOOL_ADOPTION,
    MaturityAxis.TEAM_READINESS,
    MaturityAxis.DATA_ACCESS,
    MaturityAxis.EVALUATION_SYSTEM,
)


class AxisScore(BaseModel):
    axis: MaturityAxis
    score: int = Field(ge=1, le=5, description="1~5점 자가진단 추정 점수")
    interpretation: str = Field(
        description="점수에 대한 짧은 해석 코멘트. 예: '허용된 팀 표준 AI 도구가 없음'"
    )


class Benchmark(BaseModel):
    """SPEC 2.6 — 출처가 있는 경우에만 사용하는 외부 통계 비교 코멘트."""

    comment: str
    source: str = Field(description="반드시 출처를 명시 (예: '원티드 AX 인사이트 리포트, 2026')")


class MaturityDiagnosis(BaseModel):
    goal_id: str = Field(description="같은 세션의 목표 정의서(GoalDefinition)와 잇는 식별자")
    axis_scores: list[AxisScore] = Field(description="5개 축 각각의 점수 (레이더 차트 데이터)")
    priority_axes: list[MaturityAxis] = Field(
        default_factory=list,
        description="먼저 개선해야 할 축을 우선순위 순으로 (보통 점수가 낮은 축)",
    )
    summary: str = Field(description="현재 성숙도 상태를 1~2문장으로 요약")
    benchmark: Benchmark | None = None
