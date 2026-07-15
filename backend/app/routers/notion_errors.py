"""라우터 공통 — Notion 발행 실패를 원인이 보이는 HTTP 상태코드로 바꾼다.

- `ValueError` (계정 미연결 등 사용자가 고칠 수 있는 상태) -> 400
- `httpx.HTTPStatusError` (Notion API 자체가 요청을 거절, 예: 스키마 검증 실패) -> 422

502/504는 일부러 쓰지 않는다 — Cloudflare가 이 상태코드는 origin이 실제로 뭘 응답했든 그대로
보여주지 않고 자체 브랜드 에러 페이지로 덮어써버린다. 그 결과 앱이 정확한 원인(예: "Layer is
expected to be number.")을 detail에 담아 502로 응답해도 브라우저에는 Cloudflare의 범용
"502 Bad Gateway" 페이지만 보이고 실제 원인은 완전히 가려진다 — 실 운영에서 겪은 사고
(2026-07-15). 4xx는 Cloudflare가 origin 응답을 그대로 통과시킨다.
"""

from fastapi import HTTPException


def raise_publish_error(e: Exception) -> None:
    status = 400 if isinstance(e, ValueError) else 422
    raise HTTPException(status_code=status, detail=str(e)) from e
