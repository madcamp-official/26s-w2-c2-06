"""
notion/schemas.py

팀원 / Opportunity Map / Roadmap 3개 데이터베이스의 속성 스키마(생성용)와,
행 생성·갱신 시 넣는 속성 값(rich_text/select/relation/number 등)을 만드는 헬퍼.

Progress formula 표현식은 사용자가 준 Notion 템플릿의 "기존/현재/목표 값 → 진행률" 계산을
일반화한 것이다(시간뿐 아니라 임의 지표에 적용 가능하도록 기존값→목표값 방향을 abs로 처리).
**주의**: 이 파일의 database 생성·formula 호출은 실제 Notion 워크스페이스로 라이브 검증되지
않았다(SPRINT1_FEATURE4_ROADMAP_GENERATOR.md 9절 — API 버전별 요청/응답 형태 차이가 있을 수 있어
실제 계정 연결 후 스모크 테스트가 필요).
"""

from app.contracts.roadmap import FitnessVerdict, FrequencyBucket, TaskCategory

TEAM_TITLE_PROP = "팀원"
OPPORTUNITY_TITLE_PROP = "업무"
ROADMAP_TITLE_PROP = "Task"


def _select_schema(options: list[str]) -> dict:
    return {"select": {"options": [{"name": option} for option in options]}}


def team_properties_schema() -> dict:
    return {
        TEAM_TITLE_PROP: {"title": {}},
        "강점": {"rich_text": {}},
        "AI 활용 편안함": {"rich_text": {}},
        "업무부담": {"rich_text": {}},
    }


def opportunity_map_properties_schema() -> dict:
    return {
        OPPORTUNITY_TITLE_PROP: {"title": {}},
        "빈도": _select_schema([b.value for b in FrequencyBucket]),
        "적합성": _select_schema([v.value for v in FitnessVerdict]),
        "Layer": {"number": {"format": "number"}},
        "pivot 사유": {"rich_text": {}},
    }


_PROGRESS_FORMULA_EXPRESSION = (
    'if(prop("목표값") == prop("기존값"), 1, '
    'min(1, max(0, (prop("현재값") - prop("기존값")) / (prop("목표값") - prop("기존값")))))'
)


def roadmap_properties_schema(opportunity_data_source_id: str, team_data_source_id: str) -> dict:
    return {
        ROADMAP_TITLE_PROP: {"title": {}},
        "category": _select_schema([c.value for c in TaskCategory]),
        "지표명": {"rich_text": {}},
        "단위": {"rich_text": {}},
        "기존값": {"number": {"format": "number"}},
        "현재값": {"number": {"format": "number"}},
        "목표값": {"number": {"format": "number"}},
        "Objective": {
            "relation": {"data_source_id": opportunity_data_source_id, "single_property": {}}
        },
        "담당자": {"relation": {"data_source_id": team_data_source_id, "single_property": {}}},
        "Progress": {"formula": {"expression": _PROGRESS_FORMULA_EXPRESSION}},
    }


def title_value(content: str) -> dict:
    return {"title": [{"type": "text", "text": {"content": content}}]}


def rich_text_value(content: str) -> dict:
    return {"rich_text": [{"type": "text", "text": {"content": content}}]}


def select_value(name: str | None) -> dict:
    return {"select": ({"name": name} if name else None)}


def number_value(value: float | None) -> dict:
    return {"number": value}


def relation_value(page_ids: list[str]) -> dict:
    return {"relation": [{"id": page_id} for page_id in page_ids]}
