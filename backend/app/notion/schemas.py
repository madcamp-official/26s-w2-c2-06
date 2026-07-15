"""
notion/schemas.py

팀원 / Opportunity Map / Roadmap 3개 데이터베이스의 속성 스키마(생성용)와,
행 생성·갱신 시 넣는 속성 값(rich_text/select/relation/number 등)을 만드는 헬퍼.

Progress formula 표현식은 사용자가 준 Notion 템플릿의 "기존/현재/목표 값 → 진행률" 계산을
일반화한 것이다(시간뿐 아니라 임의 지표에 적용 가능하도록 기존값→목표값 방향을 abs로 처리).

2026-07-15: database 생성·formula·dual relation·rollup 호출을 실제 워크스페이스로
라이브 검증 완료(SPRINT1_FEATURE4_ROADMAP_GENERATOR.md 9절 갱신 참고). Roadmap의
Objective/담당자 relation을 `single_property`에서 `dual_property`로 바꿔 팀원/Opportunity
Map 쪽에도 역방향 relation이 자동 생성되게 하고(사용자 제공 템플릿처럼 "담당 업무"/"Task"
컬럼이 보이도록), Opportunity Map에 Roadmap.Progress를 평균 내는 "Total Progress" rollup을
추가했다. dual relation의 역방향 속성은 Notion이 자동 생성 시 `"Related to Roadmap (Objective)"`
같은 기본 이름을 붙이므로, 생성 직후 `app/notion/sync.py`가 `synced_property_name`으로 찾아
아래 상수 이름으로 개명한다(생성 시점에 이름을 직접 지정하는 API가 없음 — 실제 호출로 확인).

2026-07-15 (추가): rollup/formula 속성은 표 컬럼으로는 멀쩡히 보이지만, **차트 뷰의 x축/y축
집계 대상으로 쓰면 "차트 데이터에 문제가 있습니다" 오류가 뜬다** — 순수 number/checkbox 속성으로
바꿔서 대조 실험해 확인함(라이브 검증). 그래서 차트에 쓰는 두 값("착수 여부", 팀원별 진행률)은
Notion formula/rollup이 아니라 `app/notion/sync.py`가 RoadmapResult에서 직접 계산해 순수
값(checkbox/number)으로 써넣는다 — "Progress"(task 개별 진행률)와 "Total Progress"(Opportunity
Map의 rollup)는 어떤 차트의 축으로도 안 쓰이는 표시 전용 컬럼이라 그대로 formula/rollup 유지.
"""

from app.contracts.maturity import MATURITY_AXES
from app.contracts.roadmap import FitnessVerdict, FrequencyBucket, TaskCategory

TEAM_TITLE_PROP = "팀원"
OPPORTUNITY_TITLE_PROP = "업무"
OPPORTUNITY_FITNESS_PROP = "적합성"
OPPORTUNITY_LAYER_PROP = "Layer"
ROADMAP_TITLE_PROP = "Task"
ROADMAP_STARTED_PROP = "착수 여부"
ROADMAP_WEEK_PROP = "주차"

# Roadmap DB 생성 시 붙이는 relation 속성 이름 — 역방향 relation의 synced_property_name으로
# 그대로 되돌아오므로, sync.py가 개명 대상을 찾을 때 이 상수를 그대로 재사용한다. 생성 직후
# ROADMAP_WORK_ITEM_RELATION_PROP("업무")로 다시 개명하므로, 값을 써넣을 땐(_upsert_task)
# 개명 후 이름을 써야 한다 — "Objective"는 개명 전 한 순간만 존재하는 임시 이름이다.
ROADMAP_OBJECTIVE_RELATION_PROP = "Objective"
ROADMAP_MEMBER_RELATION_PROP = "담당자"

# 위 relation들의 역방향(자동 생성) 속성 + Roadmap 자신의 정방향 속성을 최종적으로 개명할 이름 —
# 사용자 제공 템플릿 기준(QA_amendments 2절 "Roadmap 열 순서 정렬: ... 업무(기존 Objective 명칭 변경)").
OPPORTUNITY_TASK_RELATION_PROP = "Task"
TEAM_ASSIGNED_TASK_RELATION_PROP = "담당 업무"
TEAM_PROGRESS_PROP = "Task 진행률"
ROADMAP_WORK_ITEM_RELATION_PROP = "업무"

# "AX 성숙도 진단" DB(append-only 이력) 속성 이름
MATURITY_TITLE_PROP = "진단 회차"
MATURITY_SUMMARY_PROP = "요약"
MATURITY_PRIORITY_PROP = "우선순위"

# select 옵션 색상 고정 — 안 주면 Notion이 매번 다른 색을 배정해 재발행마다 색이 바뀐다.
# 실제 select color enum(default/gray/brown/orange/yellow/green/blue/purple/pink/red)만 허용.
_FITNESS_COLORS = {
    FitnessVerdict.FIT: "green",
    FitnessVerdict.PARTIAL: "yellow",
    FitnessVerdict.UNFIT: "red",
}
_FREQUENCY_COLORS = {
    FrequencyBucket.DAILY: "red",
    FrequencyBucket.WEEKLY: "orange",
    FrequencyBucket.BIWEEKLY: "yellow",
    FrequencyBucket.MONTHLY: "gray",
}
_CATEGORY_COLORS = {
    TaskCategory.TOOL: "blue",
    TaskCategory.AUTOMATION: "purple",
    TaskCategory.KNOWLEDGE: "green",
    TaskCategory.WORKFLOW: "orange",
    TaskCategory.CULTURE: "pink",
}
# Layer 1/2/3(SPEC 2.2) — 데모 페이지의 Layer 배지 색과 맞췄다(초록/주황/빨강, index.html의
# --l1/--l2/--l3). 라이브 검증(2026-07-15): Notion 차트 뷰의 x_axis/y_axis "type"은
# select/multi_select/status/.../formula 중 하나여야 하고 "number"는 허용되지 않는다 —
# 그래서 Layer를 number가 아니라 select로 만들어야 "AX 기회" 도넛 차트에서 그룹핑 축으로 쓸 수 있다.
_LAYER_LABELS = {1: "Layer 1", 2: "Layer 2", 3: "Layer 3"}
_LAYER_COLORS = {1: "green", 2: "yellow", 3: "red"}


def layer_select_name(layer: int | None) -> str | None:
    return _LAYER_LABELS.get(layer) if layer is not None else None


def _select_schema(colored_options: list[tuple[str, str]]) -> dict:
    return {"select": {"options": [{"name": name, "color": color} for name, color in colored_options]}}


def team_properties_schema() -> dict:
    return {
        TEAM_TITLE_PROP: {"title": {}},
        "주요 업무": {"rich_text": {}},
        "강점": {"rich_text": {}},
        "AI 활용 편안함": {"rich_text": {}},
        "업무부담": {"rich_text": {}},
        "비고": {"rich_text": {}},
        # rollup이 아니라 순수 number — 차트(Task별 진행률)의 y축으로 쓰려면 rollup/formula가 아닌
        # 값이어야 한다(위 docstring 참고). sync.py가 RoadmapResult에서 직접 평균을 계산해 써넣는다.
        TEAM_PROGRESS_PROP: {"number": {"format": "number"}},
    }


def opportunity_map_properties_schema() -> dict:
    return {
        OPPORTUNITY_TITLE_PROP: {"title": {}},
        "빈도": _select_schema([(b.value, _FREQUENCY_COLORS[b]) for b in FrequencyBucket]),
        OPPORTUNITY_FITNESS_PROP: _select_schema([(v.value, _FITNESS_COLORS[v]) for v in FitnessVerdict]),
        OPPORTUNITY_LAYER_PROP: _select_schema(
            [(label, _LAYER_COLORS[layer]) for layer, label in _LAYER_LABELS.items()]
        ),
        "pivot 사유": {"rich_text": {}},
    }


_PROGRESS_FORMULA_EXPRESSION = (
    'if(prop("목표값") == prop("기존값"), 1, '
    'min(1, max(0, (prop("현재값") - prop("기존값")) / (prop("목표값") - prop("기존값")))))'
)


def roadmap_properties_schema() -> dict:
    """Objective/담당자 relation은 여기 넣지 않는다 — Opportunity Map·팀원 DB가 아직 존재하지
    않는 시점(Roadmap을 가장 먼저 만드는 순서, sync.py `_ensure_workspace` 참고)에 스키마가
    만들어지므로, 두 DB가 생긴 뒤 `relation_properties_to_attach`로 따로 덧붙인다."""
    return {
        ROADMAP_TITLE_PROP: {"title": {}},
        ROADMAP_WEEK_PROP: {"number": {"format": "number"}},
        "category": _select_schema([(c.value, _CATEGORY_COLORS[c]) for c in TaskCategory]),
        "지표명": {"rich_text": {}},
        "단위": {"rich_text": {}},
        "기존값": {"number": {"format": "number"}},
        "현재값": {"number": {"format": "number"}},
        "목표값": {"number": {"format": "number"}},
        "Progress": {"formula": {"expression": _PROGRESS_FORMULA_EXPRESSION}},
        # formula가 아니라 순수 checkbox — "AX 적용 현황" 차트의 집계 대상으로 쓰려면 rollup/formula가
        # 아닌 값이어야 한다(위 docstring 참고). sync.py가 기존값/현재값 비교로 직접 계산해 써넣는다.
        ROADMAP_STARTED_PROP: {"checkbox": {}},
    }


def roadmap_relation_properties(opportunity_data_source_id: str, team_data_source_id: str) -> dict:
    """Opportunity Map·팀원 DB가 생성된 뒤 Roadmap에 PATCH로 덧붙이는 두 relation 속성."""
    return {
        ROADMAP_OBJECTIVE_RELATION_PROP: {
            "relation": {"data_source_id": opportunity_data_source_id, "dual_property": {}}
        },
        ROADMAP_MEMBER_RELATION_PROP: {
            "relation": {"data_source_id": team_data_source_id, "dual_property": {}}
        },
    }


def maturity_properties_schema() -> dict:
    """"AX 성숙도 진단" DB — 발행할 때마다 새 행을 추가하는 이력(append-only) 테이블이라
    upsert 대상 키가 없다(진단은 재평가할 때마다 새 회차로 쌓인다, QA_amendments 2절)."""
    properties: dict = {
        MATURITY_TITLE_PROP: {"title": {}},
        MATURITY_SUMMARY_PROP: {"rich_text": {}},
        MATURITY_PRIORITY_PROP: {"rich_text": {}},
    }
    for axis in MATURITY_AXES:
        properties[axis.value] = {"number": {"format": "number"}}
    return properties


def opportunity_progress_rollup_property(task_relation_property_name: str) -> dict:
    """Opportunity Map에 Roadmap DB로 잇는 relation(개명 후 이름)을 넘겨받아, 그 relation을 통해
    연결된 task들의 Progress 평균을 보여주는 rollup 속성을 만든다. dual relation이 실제로 생성된
    뒤에만 호출 가능하다(relation_property_name이 Opportunity Map 쪽에 존재해야 함). 표시 전용
    컬럼이라 어떤 차트에도 쓰이지 않아 rollup으로 둬도 문제없다."""
    return {
        "Total Progress": {
            "rollup": {
                "relation_property_name": task_relation_property_name,
                "rollup_property_name": "Progress",
                "function": "average",
            }
        }
    }


def title_value(content: str) -> dict:
    return {"title": [{"type": "text", "text": {"content": content}}]}


def rich_text_value(content: str) -> dict:
    return {"rich_text": [{"type": "text", "text": {"content": content}}]}


def select_value(name: str | None) -> dict:
    return {"select": ({"name": name} if name else None)}


def number_value(value: float | None) -> dict:
    return {"number": value}


def checkbox_value(value: bool) -> dict:
    return {"checkbox": value}


def relation_value(page_ids: list[str]) -> dict:
    return {"relation": [{"id": page_id} for page_id in page_ids]}
