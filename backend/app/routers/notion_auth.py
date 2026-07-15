from fastapi import APIRouter
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel

from app.core.db import get_session
from app.notion.oauth import build_authorize_url, exchange_code_for_token, find_default_page_id
from app.notion.repository import delete_connection, get_connection, save_connection

router = APIRouter(prefix="/notion", tags=["notion-auth"])


class ConnectionStatusResponse(BaseModel):
    connected: bool
    workspace_name: str | None = None


class DisconnectResponse(BaseModel):
    disconnected: bool


def _page(heading: str, message: str) -> HTMLResponse:
    return HTMLResponse(f"""
    <!doctype html>
    <html lang="ko">
    <head>
      <meta charset="utf-8" />
      <title>Notion 연결</title>
      <style>
        body {{ font-family: -apple-system, "Apple SD Gothic Neo", sans-serif;
                display: flex; align-items: center; justify-content: center;
                height: 100vh; margin: 0; background: #fafaf9; color: #37352f; }}
        .card {{ text-align: center; padding: 40px; max-width: 420px; }}
        h1 {{ font-size: 22px; margin-bottom: 12px; }}
        p {{ font-size: 15px; line-height: 1.6; color: #6b6b6b; }}
      </style>
    </head>
    <body>
      <div class="card">
        <h1>{heading}</h1>
        <p>{message}</p>
      </div>
    </body>
    </html>
    """)


@router.get("/status", response_model=ConnectionStatusResponse)
def status(account_id: str = "default") -> ConnectionStatusResponse:
    """프론트가 발행 버튼을 누르기 전에 미리 연결 여부를 보여줄 때 쓴다(계정당 1개 연결 가정)."""
    session = get_session()
    try:
        connection = get_connection(session, account_id)
    finally:
        session.close()
    if connection is None:
        return ConnectionStatusResponse(connected=False)
    return ConnectionStatusResponse(connected=True, workspace_name=connection.workspace_name)


@router.delete("/connection", response_model=DisconnectResponse)
def disconnect(account_id: str = "default") -> DisconnectResponse:
    """연결을 끊는다 — 다른 워크스페이스로 바꾸고 싶을 때는 이걸로 초기화한 뒤 /notion/connect를
    다시 밟거나(Notion 인증 화면에서 다른 워크스페이스를 고르면 됨), 그냥 /notion/connect를
    한 번 더 밟아도 같은 account_id의 연결 정보는 덮어써진다(재인증 시 save_connection이 upsert)."""
    session = get_session()
    try:
        disconnected = delete_connection(session, account_id)
    finally:
        session.close()
    return DisconnectResponse(disconnected=disconnected)


@router.get("/connect")
def connect(account_id: str = "default") -> RedirectResponse:
    """account_id를 state로 실어 Notion 인증 화면으로 보낸다. 데모용 기본값은 'default' 계정 하나.
    이미 연결된 account_id로 다시 밟아도(워크스페이스 전환 목적) 문제없다 — 콜백의 save_connection이
    upsert라 새로 인증한 워크스페이스 정보로 덮어쓴다."""
    return RedirectResponse(build_authorize_url(state=account_id))


@router.get("/callback")
def callback(state: str, code: str | None = None, error: str | None = None) -> HTMLResponse:
    if error or not code:
        return _page(
            "연결이 완료되지 않았어요",
            "Notion에서 페이지 공유를 허용하지 않으신 것 같아요. "
            f'<a href="/notion/connect?account_id={state}">다시 연결하기</a>',
        )

    token_data = exchange_code_for_token(code)
    default_page_id = find_default_page_id(token_data["access_token"])

    session = get_session()
    try:
        connection = save_connection(
            session,
            account_id=state,
            access_token=token_data["access_token"],
            refresh_token=token_data.get("refresh_token"),
            workspace_id=token_data["workspace_id"],
            workspace_name=token_data.get("workspace_name"),
            bot_id=token_data["bot_id"],
            default_page_id=default_page_id,
        )
    finally:
        session.close()

    if not connection.default_page_id:
        return _page(
            "연결은 됐는데 공유된 페이지가 없어요",
            f"'{connection.workspace_name}' 워크스페이스와 연결됐지만, integration과 공유한 페이지가 "
            f'없어서 로드맵을 어디에 보낼지 몰라요. Notion에서 페이지를 하나 공유하고 '
            f'<a href="/notion/connect?account_id={state}">다시 연결</a>해주세요.',
        )

    return _page(
        "Notion 연결 완료!",
        f"'{connection.workspace_name}' 워크스페이스에 로드맵을 보내드릴게요. "
        "이 탭은 닫으셔도 됩니다.",
    )
