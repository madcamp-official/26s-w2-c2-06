"""
roadmap/draft_plan.py

Stage A -> Stage B 내부 인터페이스. SPRINT1_FEATURE4_ROADMAP_GENERATOR.md 3절 스키마.
기능 4(로드맵 생성) 담당자 단독 소유 — 계약(SPRINT1_CONTRACT.md) 대상이 아니므로
3번 담당자 합의 없이 자유롭게 변경 가능.
"""

from pydantic import BaseModel, Field

from app.contracts.roadmap import FitnessAssessment, TaskCategory


class DraftTaskOutline(BaseModel):
    work_item_id: str = Field(
        default="", description="이 task가 어느 [wi_xxx] 업무를 구체화한 것인지 — 프롬프트의 태그를 그대로 인용"
    )
    title: str
    layer: int = Field(ge=1, le=3)
    week: int = Field(ge=1)
    category: TaskCategory
    approach: str
    source_refs: list[str] = Field(default_factory=list)


class DraftPlan(BaseModel):
    goal_id: str
    fitness_judgments: list[FitnessAssessment] = Field(default_factory=list)
    strategy_draft: str
    task_outline: list[DraftTaskOutline] = Field(default_factory=list)
    metric_ideas: list[str] = Field(default_factory=list)
    reassignment_notes: list[str] = Field(default_factory=list)
