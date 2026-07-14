"""
기능 2(AX 성숙도 진단 및 목표 설정) 파인튜닝 타겟 스키마.

app/contracts/goal.py(GoalDefinition)는 4번(로드맵 생성) 등 여러 기능이 공유하는 계약이라
그대로 두고, 이 파일은 파인튜닝 학습 데이터 생성 전용으로 별도 정의한다(공유 계약 변경 절차와
무관하게 자유롭게 조정 가능). 근거: AX리포트_부서단위_AI확산_실행계획_예시.md 2절
(5축 자가진단 표 + 목표 정의서 문장).
"""

from pydantic import BaseModel, Field


class MaturityAxis(BaseModel):
    score: int = Field(description="1~5점 정수")
    interpretation: str = Field(description="이 점수를 준 근거를 온보딩 데이터에 비춰 한두 문장으로")


class MaturityAssessment(BaseModel):
    strategy_clarity: MaturityAxis = Field(description="전략 명확성 — 무엇을 바꿀지 목표가 명확한가")
    tool_usage: MaturityAxis = Field(description="도구 활용도 — 팀 표준 도구/프롬프트가 있는가")
    team_readiness: MaturityAxis = Field(description="팀 수용력 — 팀원 간 AI 활용 편차, 거부감 수준")
    data_accessibility: MaturityAxis = Field(description="데이터 접근성 — 업무 데이터가 흩어져 있는가/모여 있는가")
    measurement_system: MaturityAxis = Field(description="평가 체계 — 시간 절감 등을 측정할 지표/습관이 있는가")


class Goal2Output(BaseModel):
    maturity: MaturityAssessment
    goal_text: str = Field(
        description=(
            "목표 정의서 한 문장. 구체적이고 측정 가능하며 실행 가능해야 한다 "
            "(예: '캠페인 성과 리포트와 카피 초안 작업의 반복 시간을 줄여 팀원들이 "
            "전략·크리에이티브 판단에 더 쓸 시간을 확보한다'). 전사 도입/큰 예산을 "
            "전제로 하지 않고, Layer3(전략적 판단) 자체를 AI가 대신하는 것처럼 들리지 않게 쓴다."
        )
    )
