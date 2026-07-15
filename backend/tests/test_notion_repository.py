import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.db import Base
from app.notion.repository import delete_connection, get_connection, save_connection


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    yield db
    db.close()


def test_save_connection_then_get_connection(session):
    save_connection(
        session,
        account_id="acc-1",
        access_token="tok-1",
        workspace_id="ws-1",
        bot_id="bot-1",
        workspace_name="내 워크스페이스",
        default_page_id="page-1",
    )

    connection = get_connection(session, "acc-1")

    assert connection is not None
    assert connection.access_token == "tok-1"
    assert connection.workspace_name == "내 워크스페이스"
    assert connection.default_page_id == "page-1"


def test_get_connection_returns_none_when_missing(session):
    assert get_connection(session, "no-such-account") is None


def test_save_connection_upserts_existing_account(session):
    save_connection(
        session, account_id="acc-1", access_token="old-tok", workspace_id="ws-1", bot_id="bot-1"
    )
    save_connection(
        session, account_id="acc-1", access_token="new-tok", workspace_id="ws-1", bot_id="bot-1"
    )

    connection = get_connection(session, "acc-1")
    assert connection.access_token == "new-tok"


def test_delete_connection_removes_existing_and_reports_true(session):
    save_connection(
        session, account_id="acc-1", access_token="tok-1", workspace_id="ws-1", bot_id="bot-1"
    )

    result = delete_connection(session, "acc-1")

    assert result is True
    assert get_connection(session, "acc-1") is None


def test_delete_connection_reports_false_when_nothing_to_delete(session):
    assert delete_connection(session, "no-such-account") is False
