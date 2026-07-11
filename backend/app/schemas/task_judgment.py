"""
schemas/task_judgment.py

Step1 LLM 판정 로직(반복성/표준화/AI위험도/AI적합성) 출력 스키마.
해당 판정 모듈이 아직 구현되지 않아, opportunity_formatter.py 개발을 위해
임시로 정의한 계약이다. 실제 판정 모듈 담당자와 필드 확정 후 갱신할 것.

task_id로 schemas/bp_matching.py의 BPMatchResult와 짝을 맞춘다.
"""

from enum import Enum

from pydantic import BaseModel, Field


class RecommendationType(str, Enum):
    TOOL = "Tool"
    AUTOMATION = "Automation"
    KNOWLEDGE = "Knowledge"
    WORKFLOW = "Workflow"
    CULTURE = "Culture"


class TaskJudgment(BaseModel):
    """업무 하나에 대한 LLM 판정 결과. RAG 매칭과는 독립적으로 생성된다."""

    task_id: str = Field(..., description="BPMatchResult.task_id와 동일해야 함")
    task_name: str
    category: str
    layer: int
    recommendation_type: RecommendationType
    is_ai_assistable: bool
    current_time_minutes: float = Field(gt=0, description="Before: 자가진단 소요시간(분)")
    expected_time_saved_minutes: float | None = Field(default=None, ge=0)
    expected_reduction_rate: float | None = Field(default=None, ge=0, le=1)
    prompt_or_guide: str | None = None


# ── 판정 모듈 구현 전까지 포맷터 개발/테스트용 더미 데이터 ──
# schemas/bp_matching.py의 DUMMY_MATCH_RESULT(task_id="task_0007")와 짝을 이룬다.
DUMMY_JUDGMENT = TaskJudgment(
    task_id="task_0007",
    task_name="원자재 단가 자료 정리 후 주간 보고서 작성",
    category="문서작성",
    layer=2,
    recommendation_type=RecommendationType.WORKFLOW,
    is_ai_assistable=True,
    current_time_minutes=90,
    expected_time_saved_minutes=45,
    prompt_or_guide="원자재 단가 원본 데이터를 표로 정리한 뒤, 아래 프롬프트로 주간 보고서 초안을 생성하세요.",
)
