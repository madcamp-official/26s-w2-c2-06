"""기능 3 — BP 리서치 엔진 (research/).

RAG의 "R": 실시간 웹서치(Gemini + Google Search grounding)로 외부 컨텍스트를 조사·요약해
`ResearchContext`를 만든다. 생성·판단은 하지 않는다 (계약 §2.1).

경계는 함수 하나뿐: `run_research(goal: GoalDefinition) -> ResearchContext` (계약 §2.3).
"""

from app.research.service import run_research

__all__ = ["run_research"]
