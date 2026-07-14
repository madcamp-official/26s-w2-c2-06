"""Gemini structured-output(response_schema)로 넘기는 pydantic 모델이 Gemini가 거부하는
제약을 쓰지 않는지 검사한다.

배경: `Field(gt=0)`은 JSON 스키마에 `exclusiveMinimum`을 넣는데, google-genai의 `Schema`는
이 키를 허용하지 않아(extra_forbidden) 런타임에 500이 난다. `ge=`(→ `minimum`)는 허용된다.
그래서 Gemini에 넘기는 스키마에서는 `exclusiveMinimum/Maximum`이 나오면 안 된다.
"""

import pytest

from app.diagnosis.draft import DiagnosisDraft
from app.onboarding.extract import TaskCandidates
from app.roadmap.draft_plan import DraftPlan
from app.contracts.roadmap import RoadmapResult

# generate_structured(client, prompt, schema)의 schema로 실제 쓰이는 모델들
GEMINI_RESPONSE_SCHEMAS = [TaskCandidates, DiagnosisDraft, DraftPlan, RoadmapResult]

_FORBIDDEN_KEYS = {"exclusiveMinimum", "exclusiveMaximum"}


def _walk(node):
    if isinstance(node, dict):
        for k, v in node.items():
            yield k
            yield from _walk(v)
    elif isinstance(node, list):
        for item in node:
            yield from _walk(item)


@pytest.mark.parametrize("schema", GEMINI_RESPONSE_SCHEMAS, ids=lambda s: s.__name__)
def test_gemini_response_schema_has_no_exclusive_bounds(schema):
    keys = set(_walk(schema.model_json_schema()))
    offending = keys & _FORBIDDEN_KEYS
    assert not offending, (
        f"{schema.__name__}에 Gemini가 거부하는 제약 {offending}이 있습니다. "
        f"수치 제약은 gt/lt 대신 ge/le를 쓰거나 제거하세요."
    )
