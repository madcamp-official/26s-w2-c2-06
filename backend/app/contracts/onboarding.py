"""
contracts/onboarding.py

1번(온보딩 인터뷰) 산출물 스키마. 기능 1의 출력이자 기능 2·4의 입력이다 (SPEC.md 4.1).

- `RepetitiveTask` / `TeamMemberTag` : SPEC 4.1 "반복 업무 상세" · "(선택) 팀원 태깅"
- `OrgEnvironment`                   : SPEC 4.1 "조직 환경" (가이드라인·지정 도구·외부 AI·편차)
- `OnboardingData`                   : 팀 프로필 + 반복 업무 + 팀원 태깅 (기능 2가 목표 정의서를 만들 때,
                                       기능 4가 로드맵을 만들 때 입력으로 쓴다)

공동 소유 — 변경 시 SPRINT1_CONTRACT.md 8절 절차(계약 먼저 갱신 → 상대 담당자 확인)를 따른다.
2026-07-14: 기능 1 구현과 함께 §8 절차로 정식화 (§1.1 임시 스키마 → 확정). `ai_adoption_level`·
`org_environment`을 **기본값과 함께 추가**해 기능 4(로드맵)의 기존 입력을 깨지 않는다.
"""

from enum import Enum

from pydantic import BaseModel, Field


class AiAdoptionLevel(str, Enum):
    """SPEC 4.1 'AI 활용 수준' 4단계."""

    NONE = "안 씀"
    TRIED = "궁금해서 써봄"
    OCCASIONAL = "가끔 필요할 때 씀"
    ACTIVE = "업무에 적극 활용"


class OrgEnvironment(BaseModel):
    """SPEC 4.1 '조직 환경'. 기능 2가 목표 정의서의 조직 제약(OrgConstraints)으로 매핑하고,
    기능 4의 게이트 판정('회사 AI 가이드라인 없음 + 민감정보')에도 근거가 된다."""

    has_ai_guideline: bool = Field(
        default=False, description="회사 차원의 AI 사용 가이드라인이 있는지"
    )
    designated_ai_tools: list[str] = Field(
        default_factory=list, description="사내에서 공식 지정한 AI 도구 (없으면 빈 배열)"
    )
    external_ai_allowed: bool = Field(
        default=False, description="외부 AI 도구(예: 개인 ChatGPT) 사용이 허용되는지"
    )
    ai_usage_variance: str = Field(
        default="",
        description="팀원 간 AI 활용 수준 편차. 예: '큼(2명 적극·나머지 미사용)'",
    )


class RepetitiveTask(BaseModel):
    title: str
    frequency: str = Field(description="예: '주 1회 이상'(자주) / '월 1회 이하'(가끔)")
    is_standardized: bool = Field(description="매번 비슷한 방식으로 처리되는지 (정형 여부)")
    avg_time_minutes: float = Field(gt=0)
    contains_sensitive_info: bool = False
    current_method: str = Field(description="기존 처리 방식 (예: '엑셀 수기 작성')")


class TeamMemberTag(BaseModel):
    member_id: str = Field(description="익명 식별자 — 실명 사용 금지 (SPEC.md 4.1·2.6 정책)")
    strengths: list[str] = Field(default_factory=list)
    ai_comfort_level: str = Field(description="예: 낮음/중간/높음")
    workload_level: str = Field(description="예: 낮음/중간/높음")


class OnboardingData(BaseModel):
    team_size: int = Field(gt=0)
    industry: str | None = None
    work_categories: list[str] = Field(
        default_factory=list, description="담당 업무 카테고리 (SPEC 4.1 기본 정보)"
    )
    ai_adoption_level: AiAdoptionLevel = Field(
        default=AiAdoptionLevel.NONE, description="SPEC 4.1 AI 활용 수준 4단계"
    )
    org_environment: OrgEnvironment = Field(default_factory=OrgEnvironment)
    repetitive_tasks: list[RepetitiveTask] = Field(default_factory=list)
    member_tags: list[TeamMemberTag] = Field(default_factory=list)
