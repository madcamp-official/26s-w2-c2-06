"""
contracts/goal.py

2번(AX 성숙도 진단 및 목표 설정)의 산출물 스키마. SPRINT1_CONTRACT.md 1절 그대로 코드화.
공동 소유 — 변경 시 SPRINT1_CONTRACT.md 8절 절차(계약 먼저 갱신 → 상대 담당자 확인) 따를 것.
"""

from pydantic import BaseModel, Field


class OrgConstraints(BaseModel):
    allowed_tools: list[str] = Field(default_factory=list)
    integrated_systems: list[str] = Field(default_factory=list)
    external_ai_allowed: bool = False
    security_level: str = Field(description="예: low / medium / high")


class GoalDefinition(BaseModel):
    goal_id: str
    goal_text: str
    org_constraints: OrgConstraints
    candidate_tasks_from_onboarding: list[str] = Field(default_factory=list)
