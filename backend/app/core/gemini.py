"""
core/gemini.py

Gemini structured-output 호출을 감싸는 얇은 공용 래퍼. 기능 1(온보딩)·기능 2(진단)가 공유한다.
검색(grounding)은 사용하지 않는다 — 생성/판정만 담당한다.

(기능 4 roadmap/ 패키지는 자체 gemini_client.py를 이미 갖고 있어 그대로 두고, 여기서는
기능 1·2가 쓸 동일 패턴만 제공한다. 시그니처가 같아 테스트의 FakeClient를 그대로 재사용한다.)
"""

from typing import TypeVar

from google import genai
from google.genai import types
from pydantic import BaseModel

from app.core.config import settings

_client: genai.Client | None = None

T = TypeVar("T", bound=BaseModel)


def get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=settings.gemini_api_key)
    return _client


def generate_structured(client: genai.Client, prompt: str, schema: type[T]) -> T:
    response = client.models.generate_content(
        model=settings.gemini_model,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=schema,
        ),
    )
    if response.parsed is not None:
        return response.parsed
    return schema.model_validate_json(response.text)
