"""
diagnosis/draft.py

기능 2의 LLM(Gemini) 출력 스키마. 판단이 필요한 부분(축별 점수·해석·우선순위·목표 문장)만
LLM이 만들고, 조직 제약(허용 도구·외부 AI·보안 수준) 같은 사실값은 service가 온보딩에서
결정론적으로 채운다 — LLM이 조직 제약을 지어내지 않도록 분리한다 (SPEC 2.6).

기능 2 단독 소유(내부 인터페이스) — contracts 대상이 아니다.
"""

from pydantic import BaseModel, Field

from app.contracts.maturity import AxisScore, Benchmark, MaturityAxis


class DiagnosisDraft(BaseModel):
    axis_scores: list[AxisScore] = Field(description="5개 축(전략 명확성/도구 활용도/팀 수용력/데이터 접근성/평가 체계) 점수")
    priority_axes: list[MaturityAxis] = Field(
        default_factory=list, description="먼저 개선할 축을 우선순위 순으로"
    )
    summary: str = Field(description="현재 성숙도 상태 1~2문장 요약")
    benchmark: Benchmark | None = Field(
        default=None, description="출처를 댈 수 있는 외부 통계 비교. 확신 없으면 null (SPEC 2.6)"
    )
    goal_text: str = Field(
        description="문제 정의 → AI로 해결을 담은 한 문장짜리 목표 정의서 (SPEC 4.2 목표 설정)"
    )
    integrated_systems: list[str] = Field(
        default_factory=list,
        description="반복 업무의 현재 처리 방식에서 언급된 연동 대상 시스템 (예: ERP, 대시보드). 없으면 빈 배열",
    )
