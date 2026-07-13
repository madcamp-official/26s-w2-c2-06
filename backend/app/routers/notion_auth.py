from fastapi import APIRouter
from fastapi.responses import HTMLResponse, RedirectResponse

from app.core.db import get_session
from app.notion.oauth import build_authorize_url, exchange_code_for_token, find_default_page_id
from app.notion.repository import save_connection

router = APIRouter(prefix="/notion", tags=["notion-auth"])


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


@router.get("/connect")
def connect(account_id: str = "default") -> RedirectResponse:
    """account_id를 state로 실어 Notion 인증 화면으로 보낸다. 데모용 기본값은 'default' 계정 하나."""
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
