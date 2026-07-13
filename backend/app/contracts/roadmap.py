"""
contracts/roadmap.py

4번(로드맵 생성) -> Frontend / 5번(트래킹) 인터페이스. SPRINT1_CONTRACT.md 5절 스키마 그대로 코드화.
공동 소유 — 변경 시 SPRINT1_CONTRACT.md 8절 절차 따를 것. 실제 생성 로직은 app/roadmap/ 소유.
"""

from pydantic import BaseModel, Field

from app.contracts.research import ResearchStatus

ROLE_REASSIGNMENT_DISCLAIMER = "실제 배분은 팀장님이 판단해주세요"


class FitnessAssessment(BaseModel):
    task_candidate: str
    matrix_position: str = Field(description="예: '자주+정형', '가끔+비정형'")
    verdict: str
    reason: str
    gate_applied: str | None = None


class Task(BaseModel):
    task_id: str
    title: str
    layer: int = Field(ge=1, le=3)
    week: int = Field(ge=1)
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
    suggested_member: str
    reason: str
    disclaimer: str = ROLE_REASSIGNMENT_DISCLAIMER


class Metric(BaseModel):
    task_id: str
    metric_name: str
    baseline: str
    target: str


class RoadmapResult(BaseModel):
    goal_id: str
    research_status: ResearchStatus
    fitness_assessment: list[FitnessAssessment] = Field(default_factory=list)
    tasks: list[Task] = Field(default_factory=list)
    role_reassignment_suggestions: list[RoleReassignmentSuggestion] = Field(default_factory=list)
    metrics: list[Metric] = Field(default_factory=list)
