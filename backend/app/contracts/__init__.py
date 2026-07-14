"""공통 계약 스키마 (contracts).

`SPRINT1_CONTRACT.md`의 인터페이스 계약을 pydantic v2로 코드화한 패키지.
- `onboarding.py` : OnboardingData (SPEC 4.1, 기능 1 → 2·4 입력)
- `goal.py`       : GoalDefinition (계약 §1, 기능 2 → 3·4 입력)
- `maturity.py`   : MaturityDiagnosis (SPEC 4.2, 기능 2 → 노션 페이지)
- `research.py`   : ResearchContext / Finding (계약 §4, 기능 3 → 4)
- `roadmap.py`    : RoadmapResult (계약 §5, 기능 4 → 프론트/5)

이 패키지는 공동 소유다. 스키마 변경은 계약 §8 절차(문서 먼저 갱신 → 상대 담당자 확인 → 코드 반영)를 따른다.
"""

from app.contracts.goal import GoalDefinition, OrgConstraints
from app.contracts.maturity import (
    MATURITY_AXES,
    AxisScore,
    Benchmark,
    MaturityAxis,
    MaturityDiagnosis,
)
from app.contracts.onboarding import (
    AiAdoptionLevel,
    OnboardingData,
    OrgEnvironment,
    RepetitiveTask,
    TeamMemberTag,
)
from app.contracts.research import Finding, ResearchContext

__all__ = [
    "GoalDefinition",
    "OrgConstraints",
    "AiAdoptionLevel",
    "OnboardingData",
    "OrgEnvironment",
    "RepetitiveTask",
    "TeamMemberTag",
    "MaturityAxis",
    "MATURITY_AXES",
    "AxisScore",
    "Benchmark",
    "MaturityDiagnosis",
    "Finding",
    "ResearchContext",
]
