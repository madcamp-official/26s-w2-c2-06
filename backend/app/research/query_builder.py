"""검색 쿼리 빌드 (FEATURE3 §4).

`goal_text` + `org_constraints`로 소스 API용 쿼리 2~4개를 생성한다.
논문 API(Semantic Scholar/arXiv)는 영문 키워드에 강하고 한글 목표 문장에는 약하므로,
스프린트1은 조직 제약(허용 도구·연동 시스템) + AX/LLM 일반 키워드를 조합한다.
(한글 목표 → 정밀 키워드 추출은 LLM 확보 시 승격 — 오픈 이슈)
사용한 쿼리는 `ResearchContext.search_queries`에 그대로 기록된다.
"""

from __future__ import annotations

from app.contracts import GoalDefinition

# SPEC 4.3 리서치 대상(트렌드/논문/활용법)에 대응하는 AX·LLM 일반 관점
_BASE_QUERIES = [
    "large language model workplace productivity",
    "generative AI enterprise adoption best practice",
]


def build_search_queries(goal: GoalDefinition) -> list[str]:
    oc = goal.org_constraints
    queries: list[str] = []

    # 관점 1: 허용 도구 특화 (예: "Copilot enterprise adoption")
    tools = " ".join(oc.allowed_tools).strip()
    if tools:
        queries.append(f"{tools} enterprise adoption")

    # 관점 2~3: AX/LLM 일반 (트렌드·연구)
    queries.extend(_BASE_QUERIES)

    # 관점 4: 연동 시스템 특화 (예: "ERP AI automation")
    if oc.integrated_systems:
        systems = " ".join(oc.integrated_systems).strip()
        queries.append(f"{systems} AI automation")

    # 공백 정규화 + 중복 제거(순서 유지) + 최대 4개
    seen: set[str] = set()
    out: list[str] = []
    for q in queries:
        qn = " ".join(q.split())
        if qn and qn not in seen:
            seen.add(qn)
            out.append(qn)
    return out[:4]
