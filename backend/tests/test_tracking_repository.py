import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.db import Base
from app.notion.tracking_repository import (
    WorkspaceRecord,
    forget_workspace,
    get_member_page_id,
    get_task_page_id,
    get_work_item_page_id,
    get_workspace,
    save_maturity_database,
    save_member_page,
    save_task_page,
    save_work_item_page,
    save_workspace,
)


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    yield db
    db.close()


def _workspace_record(account_id: str = "acc-1") -> WorkspaceRecord:
    return WorkspaceRecord(
        account_id=account_id,
        team_database_id="team-db",
        team_data_source_id="team-ds",
        opportunity_database_id="opp-db",
        opportunity_data_source_id="opp-ds",
        roadmap_database_id="roadmap-db",
        roadmap_data_source_id="roadmap-ds",
        dashboard_page_id="dash-page",
        dashboard_url="https://notion.so/dash-page",
        goal_callout_block_id="goal-block",
    )


def test_save_then_get_workspace(session):
    save_workspace(session, _workspace_record())

    record = get_workspace(session, "acc-1")

    assert record is not None
    assert record.team_data_source_id == "team-ds"
    assert record.dashboard_url == "https://notion.so/dash-page"


def test_save_workspace_upserts_existing_record(session):
    save_workspace(session, _workspace_record())
    updated = _workspace_record()
    updated.goal_callout_block_id = "new-block"
    save_workspace(session, updated)

    record = get_workspace(session, "acc-1")
    assert record.goal_callout_block_id == "new-block"


def test_get_workspace_returns_none_when_missing(session):
    assert get_workspace(session, "no-such-account") is None


def test_member_page_save_then_get(session):
    save_member_page(session, "acc-1", "M1", "member-page-1")

    assert get_member_page_id(session, "acc-1", "M1") == "member-page-1"
    assert get_member_page_id(session, "acc-1", "M2") is None


def test_work_item_page_save_then_get_scoped_by_goal(session):
    save_work_item_page(session, "acc-1", "goal_001", "wi_001", "wi-page-1")

    assert get_work_item_page_id(session, "acc-1", "goal_001", "wi_001") == "wi-page-1"
    # 다른 goal_id에서는 같은 work_item_id라도 못 찾는다 (goal 단위로만 유일)
    assert get_work_item_page_id(session, "acc-1", "goal_002", "wi_001") is None


def test_task_page_save_then_get_scoped_by_goal(session):
    save_task_page(session, "acc-1", "goal_001", "task_001", "task-page-1")

    assert get_task_page_id(session, "acc-1", "goal_001", "task_001") == "task-page-1"
    assert get_task_page_id(session, "acc-1", "goal_002", "task_001") is None


def test_save_maturity_database_updates_existing_workspace(session):
    save_workspace(session, _workspace_record())

    save_maturity_database(session, "acc-1", "maturity-db", "maturity-ds")

    record = get_workspace(session, "acc-1")
    assert record.maturity_database_id == "maturity-db"
    assert record.maturity_data_source_id == "maturity-ds"


def test_save_maturity_database_noop_when_workspace_missing(session):
    # 워크스페이스가 아예 없으면 조용히 무시한다(있을 수 없는 상태를 방어)
    save_maturity_database(session, "no-such-account", "maturity-db", "maturity-ds")
    assert get_workspace(session, "no-such-account") is None


def test_forget_workspace_removes_workspace_and_all_row_mappings(session):
    save_workspace(session, _workspace_record())
    save_member_page(session, "acc-1", "M1", "member-page-1")
    save_work_item_page(session, "acc-1", "goal_001", "wi_001", "wi-page-1")
    save_task_page(session, "acc-1", "goal_001", "task_001", "task-page-1")

    forget_workspace(session, "acc-1")

    assert get_workspace(session, "acc-1") is None
    assert get_member_page_id(session, "acc-1", "M1") is None
    assert get_work_item_page_id(session, "acc-1", "goal_001", "wi_001") is None
    assert get_task_page_id(session, "acc-1", "goal_001", "task_001") is None


def test_forget_workspace_does_not_affect_other_accounts(session):
    save_workspace(session, _workspace_record("acc-1"))
    save_workspace(session, _workspace_record("acc-2"))
    save_member_page(session, "acc-2", "M1", "acc2-member-page")

    forget_workspace(session, "acc-1")

    assert get_workspace(session, "acc-1") is None
    assert get_workspace(session, "acc-2") is not None
    assert get_member_page_id(session, "acc-2", "M1") == "acc2-member-page"
