import html

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel

from app.core.db import get_session
from app.notion.oauth import build_authorize_url, exchange_code_for_token, list_shared_pages
from app.notion.repository import delete_connection, get_connection, save_connection, set_default_page

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


def _picker_page(account_id: str, workspace_name: str | None, pages: list[dict]) -> HTMLResponse:
    items = "".join(
        f'<li><a href="/notion/select-page?account_id={html.escape(account_id, quote=True)}'
        f'&page_id={html.escape(p["id"], quote=True)}">{html.escape(p["title"])}</a></li>'
        for p in pages
    )
    return HTMLResponse(f"""
    <!doctype html>
    <html lang="ko">
    <head>
      <meta charset="utf-8" />
      <title>발행할 페이지 선택</title>
      <style>
        body {{ font-family: -apple-system, "Apple SD Gothic Neo", sans-serif;
                display: flex; align-items: center; justify-content: center;
                min-height: 100vh; margin: 0; background: #fafaf9; color: #37352f; }}
        .card {{ text-align: center; padding: 40px; max-width: 480px; }}
        h1 {{ font-size: 22px; margin-bottom: 12px; }}
        p {{ font-size: 15px; line-height: 1.6; color: #6b6b6b; }}
        ul {{ list-style: none; padding: 0; margin: 20px 0 0; text-align: left; }}
        li {{ margin: 8px 0; }}
        a {{ display: block; padding: 10px 14px; border: 1px solid #e3e6ea; border-radius: 8px;
             color: #37352f; text-decoration: none; }}
        a:hover {{ background: #f0f0ee; }}
      </style>
    </head>
    <body>
      <div class="card">
        <h1>어느 페이지에 발행할까요?</h1>
        <p>'{html.escape(workspace_name or "")}' 워크스페이스에서 이 integration과 공유된 페이지가 여러 개
        보여요. 로드맵을 발행할 페이지를 하나 골라주세요.</p>
        <ul>{items}</ul>
      </div>
    </body>
    </html>
    """)


@router.get("/select-page")
def select_page(account_id: str, page_id: str) -> HTMLResponse:
    """공유된 페이지가 여러 개일 때 사용자가 고른 페이지로 발행 대상을 확정한다."""
    session = get_session()
    try:
        connection = set_default_page(session, account_id, page_id)
    finally:
        session.close()

    if connection is None:
        return _page(
            "연결을 찾을 수 없어요",
            f'<a href="/notion/connect?account_id={account_id}">Notion을 먼저 연결</a>해주세요.',
        )

    return _page(
        "발행 대상 페이지를 정했어요!",
        f"'{connection.workspace_name}' 워크스페이스의 선택한 페이지로 로드맵을 보내드릴게요. "
        "이 탭은 닫으셔도 됩니다.",
    )


@router.get("/callback")
def callback(state: str, code: str | None = None, error: str | None = None) -> HTMLResponse:
    if error or not code:
        return _page(
            "연결이 완료되지 않았어요",
            "Notion에서 페이지 공유를 허용하지 않으신 것 같아요. "
            f'<a href="/notion/connect?account_id={state}">다시 연결하기</a>',
        )

    token_data = exchange_code_for_token(code)
    pages = list_shared_pages(token_data["access_token"])
    default_page_id = pages[0]["id"] if pages else None

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

    if len(pages) > 1:
        # 첫 번째 페이지가 잠정 기본값으로 이미 저장돼 있지만, 어떤 페이지가 "첫 번째"로 오는지는
        # Notion 검색 순위에 달려 있어 재연결마다 바뀔 수 있다 — 사용자가 직접 고르게 한다
        # (2026-07-15, 자동 선택 때문에 발행 대상이 의도치 않게 바뀌는 사고가 실 운영에서 있었음).
        return _picker_page(state, connection.workspace_name, pages)

    return _page(
        "Notion 연결 완료!",
        f"'{connection.workspace_name}' 워크스페이스에 로드맵을 보내드릴게요. "
        "이 탭은 닫으셔도 됩니다.",
    )
