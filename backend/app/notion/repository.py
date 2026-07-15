"""notion_connections 테이블 접근. account_id 하나당 연결 정보 하나를 갱신(upsert)한다."""

from sqlalchemy.orm import Session

from app.notion.models import NotionConnection


def save_connection(
    session: Session,
    account_id: str,
    access_token: str,
    workspace_id: str,
    bot_id: str,
    refresh_token: str | None = None,
    workspace_name: str | None = None,
    default_page_id: str | None = None,
) -> NotionConnection:
    connection = session.get(NotionConnection, account_id)
    if connection is None:
        connection = NotionConnection(account_id=account_id)
        session.add(connection)

    connection.access_token = access_token
    connection.refresh_token = refresh_token
    connection.workspace_id = workspace_id
    connection.workspace_name = workspace_name
    connection.bot_id = bot_id
    connection.default_page_id = default_page_id

    session.commit()
    session.refresh(connection)
    return connection


def get_connection(session: Session, account_id: str) -> NotionConnection | None:
    return session.get(NotionConnection, account_id)


def delete_connection(session: Session, account_id: str) -> bool:
    """계정 연결을 끊는다(워크스페이스 전환 전 초기화, 테스트 시 미연결 상태 재현 등에 쓴다).
    연결이 있었으면 True, 애초에 없었으면 False를 반환한다."""
    connection = session.get(NotionConnection, account_id)
    if connection is None:
        return False
    session.delete(connection)
    session.commit()
    return True
