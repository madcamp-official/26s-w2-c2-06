"""테스트 공용 픽스처. Gemini를 실제로 호출하지 않는 가짜 클라이언트를 제공한다."""

from typing import Any


class FakeResponse:
    def __init__(self, parsed: Any):
        self.parsed = parsed
        self.text = ""


class FakeModels:
    def __init__(self, parsed: Any):
        self._parsed = parsed
        self.calls: list[dict] = []

    def generate_content(self, *, model, contents, config):
        self.calls.append({"model": model, "contents": contents, "config": config})
        return FakeResponse(self._parsed)


class FakeClient:
    """google.genai.Client 대신 주입하는 가짜 클라이언트. .models.generate_content만 흉내낸다."""

    def __init__(self, parsed: Any):
        self.models = FakeModels(parsed)
