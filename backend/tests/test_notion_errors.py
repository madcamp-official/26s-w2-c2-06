import httpx
import pytest
from fastapi import HTTPException

from app.routers.notion_errors import raise_publish_error


def test_value_error_maps_to_400():
    with pytest.raises(HTTPException) as exc_info:
        raise_publish_error(ValueError("계정이 연결되어 있지 않습니다."))

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "계정이 연결되어 있지 않습니다."


def test_httpx_status_error_maps_to_422_not_502():
    """Cloudflare가 502/504는 origin 응답 그대로 안 보여주고 자체 에러 페이지로 덮어써버려서
    (실 운영 사고, 2026-07-15), 이 경로는 반드시 4xx를 써야 한다."""
    request = httpx.Request("POST", "https://api.notion.com/v1/pages")
    response = httpx.Response(400, request=request, json={"message": "Layer is expected to be number."})
    error = httpx.HTTPStatusError("400 Bad Request -> Layer is expected to be number.", request=request, response=response)

    with pytest.raises(HTTPException) as exc_info:
        raise_publish_error(error)

    assert exc_info.value.status_code == 422
    assert exc_info.value.status_code not in (502, 504)
    assert "Layer is expected to be number." in exc_info.value.detail
