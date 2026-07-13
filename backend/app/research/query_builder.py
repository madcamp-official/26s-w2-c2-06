"""검색 쿼리 빌드 (FEATURE3 §4-1).

`goal_text` + `org_constraints`로 검색 관점 2~4개를 생성한다.
스프린트1은 템플릿 기반(결정적) — 도구 특화 사례 / 방법론·연구 / 실패 요인 / 연동 시스템.
(추후 LLM 기반 쿼리 생성으로 승격 가능. 계약·시그니처 불변.)
사용한 쿼리는 `ResearchContext.search_queries`에 그대로 기록된다 (디버깅·추적용).
"""

from __future__ import annotations

from app.contracts import GoalDefinition


def build_search_queries(goal: GoalDefinition) -> list[str]:
    text = goal.goal_text.strip()
    oc = goal.org_constraints

    queries: list[str] = []

    # 관점 1: 도구 특화 활용 사례
    tools = " ".join(oc.allowed_tools).strip()
    queries.append(f"{text} {tools} 활용 사례".strip() if tools else f"{text} 활용 사례")

    # 관점 2: 방법론·연구 (trend/research)
    queries.append(f"{text} 방법론 best practice research")

    # 관점 3: 실패 요인·주의사항 (SPEC 2.3 AI 만능주의 경계 근거 수집)
    queries.append(f"{text} 도입 실패 요인 주의사항")

    # 관점 4: 연동 시스템 (있을 때만)
    if oc.integrated_systems:
        systems = " ".join(oc.integrated_systems).strip()
        queries.append(f"{text} {systems} 연동 자동화")

    # 공백 정규화 + 중복 제거(순서 유지) + 최대 4개
    seen: set[str] = set()
    out: list[str] = []
    for q in queries:
        qn = " ".join(q.split())
        if qn and qn not in seen:
            seen.add(qn)
            out.append(qn)
    return out[:4]
