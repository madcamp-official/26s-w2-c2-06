"""
contracts/roadmap.py

4번(로드맵 생성) -> Frontend / 5번(트래킹) / Notion 인터페이스. SPRINT1_CONTRACT.md 5절 스키마 그대로 코드화.
공동 소유 — 변경 시 SPRINT1_CONTRACT.md 8절 절차 따를 것. 실제 생성 로직은 app/roadmap/ 소유.

v0.9: Notion Opportunity Map/Roadmap 데이터베이스 발행을 위해 additive 확장
(work_item_id/fitness/layer/frequency_bucket/category/숫자 Metric/assigned_member_ids).
"""

from enum import Enum

from pydantic import BaseModel, Field

from app.contracts.research import ResearchStatus

ROLE_REASSIGNMENT_DISCLAIMER = "실제 배분은 팀장님이 판단해주세요"


class FitnessVerdict(str, Enum):
    """SPEC 4.4 매트릭스+게이트 판정을 Notion Opportunity Map의 select 값으로 정규화한 3단계."""

    FIT = "적합"
    PARTIAL = "부분 적합"
    UNFIT = "부적합"


class FrequencyBucket(str, Enum):
    """Opportunity Map '빈도' 컬럼. OnboardingData.RepetitiveTask.frequency(자유 텍스트)를
    Stage A가 해석해서 채운다 — 온보딩 스키마 자체는 바꾸지 않는다."""

    DAILY = "매일"
    WEEKLY = "매주"
    BIWEEKLY = "격주"
    MONTHLY = "월 1~2회"


class TaskCategory(str, Enum):
    """Roadmap 'category' 컬럼. 고정 5종."""

    TOOL = "Tool"
    AUTOMATION = "Automation"
    KNOWLEDGE = "Knowledge"
    WORKFLOW = "Workflow"
    CULTURE = "Culture"


class FitnessAssessment(BaseModel):
    work_item_id: str = Field(
        default="",
        description="온보딩 반복업무 순서로 코드가 강제 부여(wi_001…). LLM 출력 무시.",
    )
    task_candidate: str
    matrix_position: str = Field(description="예: '자주+정형', '가끔+비정형'")
    fitness: FitnessVerdict
    layer: int | None = Field(default=None, ge=1, le=3, description="fitness가 부적합이 아닐 때만")
    frequency_bucket: FrequencyBucket
    verdict: str
    reason: str
    gate_applied: str | None = None


class Task(BaseModel):
    task_id: str
    work_item_id: str = Field(
        default="", description="이 task가 속한 업무(FitnessAssessment.work_item_id) 참조"
    )
    title: str
    layer: int = Field(ge=1, le=3)
    week: int = Field(ge=1)
    category: TaskCategory
    difficulty: str
    est_time: str
    expected_effect: str
    tools_needed: list[str] = Field(default_factory=list)
    failure_risk: str
    source_refs: list[str] = Field(default_factory=list)
    detailed_guide: str = Field(
        default="",
        description=(
            "관련 업무를 전혀 모르는 사람도 바로 따라 할 수 있는 단계별 상세 가이드. "
            "도구 계정 생성/설정 방법, 실제로 복사해서 쓸 수 있는 예시 프롬프트 등을 포함"
        ),
    )


class RoleReassignmentSuggestion(BaseModel):
    task_id: str
    assigned_member_ids: list[str] = Field(
        default_factory=list,
        description="OnboardingData.member_tags[].member_id 중에서만 허용 — 코드가 검증",
    )
    reason: str
    disclaimer: str = ROLE_REASSIGNMENT_DISCLAIMER


class Metric(BaseModel):
    task_id: str
    metric_name: str = Field(description="예: '보고서 작성 소요시간', '요약 정확도' — 시간에 고정하지 않음")
    unit: str = Field(description="예: '분', '건', '%'")
    baseline_value: float
    current_value: float = Field(
        default=0.0, description="발행 시 baseline_value와 동일하게 코드가 강제 초기화"
    )
    target_value: float


class RoadmapResult(BaseModel):
    goal_id: str
    research_status: ResearchStatus
    fitness_assessment: list[FitnessAssessment] = Field(default_factory=list)
    tasks: list[Task] = Field(default_factory=list)
    role_reassignment_suggestions: list[RoleReassignmentSuggestion] = Field(default_factory=list)
    metrics: list[Metric] = Field(default_factory=list)
