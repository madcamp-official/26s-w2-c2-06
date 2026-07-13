"""GoalDefinition — 목표 정의서 스키마 (계약 §1).

기능 2(AX 성숙도 진단 및 목표 설정)의 산출물이자, 기능 3(리서치)·기능 4(로드맵)의 입력.
`run_research(goal: GoalDefinition) -> ResearchContext`의 입력 타입이다 (계약 §2.3).

스프린트1 표준 입력 픽스처는 `app/fixtures/goal_001.json`.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class OrgConstraints(BaseModel):
    """조직 제약 — 목표가 놓인 환경 (허용 도구, 연동 시스템, 보안 수준 등).

    리서치 쿼리 빌드(관점 생성)에 활용된다. 예: `external_ai_allowed=False`이면
    사내/온프레미스 활용 사례 관점을 우선한다.
    """

    allowed_tools: list[str] = Field(
        default_factory=list, description="허용된 AI 도구 (예: ['Copilot'])"
    )
    integrated_systems: list[str] = Field(
        default_factory=list, description="연동 시스템 (예: ['ERP'])"
    )
    external_ai_allowed: bool = Field(
        default=False, description="외부(퍼블릭) AI 도구 사용 허용 여부"
    )
    security_level: Literal["low", "medium", "high"] = Field(
        default="medium", description="보안 수준"
    )


class GoalDefinition(BaseModel):
    """목표 정의서 (기능 2 산출물). 리서치는 이 '목표 단위'로 조사한다 — task 단위 아님."""

    goal_id: str = Field(..., description="목표 식별자. 리서치 캐시 키이기도 하다 (계약 §2.4)")
    goal_text: str = Field(..., description="목표 텍스트 (조직 환경을 이미 반영한 문장)")
    org_constraints: OrgConstraints = Field(default_factory=OrgConstraints)
    candidate_tasks_from_onboarding: list[str] = Field(
        default_factory=list,
        description="1번(온보딩)에서 수집한 반복 업무 후보 (참조용). task breakdown은 기능 4 역할",
    )
