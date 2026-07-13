"""
contracts/onboarding.py

1번(온보딩 인터뷰) 산출물 스키마 — **초안(placeholder)**.
1번 담당자가 아직 정해지지 않아 4번(로드맵 생성) 개발이 막히지 않도록 SPEC.md 4.1의
"팀 프로필 + 반복 업무 리스트" 설명만 보고 임시로 정의했다.
1번 실제 담당자가 정해지면 SPRINT1_CONTRACT.md 8절 절차(계약 갱신 -> 상대 담당자 확인)로
필드를 재확인/조정할 것 — 특히 frequency/is_standardized의 정확한 판정 기준.
"""

from pydantic import BaseModel, Field


class RepetitiveTask(BaseModel):
    title: str
    frequency: str = Field(description="예: '주 1회 이상'(자주) / '월 1회 이하'(가끔)")
    is_standardized: bool = Field(description="매번 비슷한 방식으로 처리되는지 (정형 여부)")
    avg_time_minutes: float = Field(gt=0)
    contains_sensitive_info: bool = False
    current_method: str = Field(description="기존 처리 방식 (예: '엑셀 수기 작성')")


class TeamMemberTag(BaseModel):
    member_id: str = Field(description="익명 식별자 — 실명 사용 금지 (SPEC.md 4.1 정책)")
    strengths: list[str] = Field(default_factory=list)
    ai_comfort_level: str = Field(description="예: 낮음/중간/높음")
    workload_level: str = Field(description="예: 낮음/중간/높음")


class OnboardingData(BaseModel):
    team_size: int = Field(gt=0)
    industry: str | None = None
    repetitive_tasks: list[RepetitiveTask] = Field(default_factory=list)
    member_tags: list[TeamMemberTag] = Field(default_factory=list)
