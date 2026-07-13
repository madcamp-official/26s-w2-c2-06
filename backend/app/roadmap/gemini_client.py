"""
roadmap/gemini_client.py

Gemini structured-output 호출을 감싸는 얇은 래퍼. Stage A/B 모두 이 함수 하나로 호출한다.
검색(grounding)은 사용하지 않는다 — 4번(로드맵 생성)은 RAG의 "G"만 담당 (SPRINT1_CONTRACT.md 2.1절).
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
