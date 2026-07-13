"""공통 계약 스키마 (contracts).

`SPRINT1_CONTRACT.md`의 인터페이스 계약을 pydantic v2로 코드화한 패키지.
- `goal.py`     : GoalDefinition (계약 §1, 기능 2 → 3·4 입력)
- `research.py` : ResearchContext / Finding (계약 §4, 기능 3 → 4)

이 패키지는 공동 소유다. 스키마 변경은 계약 §8 절차(문서 먼저 갱신 → 상대 담당자 확인 → 코드 반영)를 따른다.
"""

from app.contracts.goal import GoalDefinition, OrgConstraints
from app.contracts.research import Finding, ResearchContext

__all__ = [
    "GoalDefinition",
    "OrgConstraints",
    "Finding",
    "ResearchContext",
]
