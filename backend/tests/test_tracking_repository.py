import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.db import Base
from app.notion.tracking_repository import (
    TrackedTask,
    get_published_roadmap,
    save_published_roadmap,
)


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    yield db
    db.close()


def test_save_then_get_published_roadmap(session):
    tasks = [
        TrackedTask(task_id="task_001", title="온보딩 정리", checkbox_block_id="block-1"),
        TrackedTask(task_id="task_002", title="보고서 자동화", checkbox_block_id="block-2"),
    ]

    save_published_roadmap(
        session, page_id="page-1", account_id="acc-1", stats_block_id="stats-1", tasks=tasks
    )

    record = get_published_roadmap(session, "page-1")

    assert record is not None
    assert record.account_id == "acc-1"
    assert record.stats_block_id == "stats-1"
    assert {t.task_id: t.checkbox_block_id for t in record.tasks} == {
        "task_001": "block-1",
        "task_002": "block-2",
    }


def test_get_published_roadmap_returns_none_when_missing(session):
    assert get_published_roadmap(session, "no-such-page") is None
