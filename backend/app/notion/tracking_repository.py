"""발행된 로드맵(page_id)과 그 안의 task 체크박스 블록 ID를 저장/조회한다.
새로고침(progress.py)이 "이 페이지의 체크박스들, 지금 몇 개 체크됐나"를 알아내는 데 쓴다."""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.notion.models import PublishedRoadmap, PublishedRoadmapTask


@dataclass
class TrackedTask:
    task_id: str
    title: str
    checkbox_block_id: str


@dataclass
class PublishedRoadmapRecord:
    page_id: str
    account_id: str
    stats_block_id: str | None
    tasks: list[TrackedTask]


def save_published_roadmap(
    session: Session,
    page_id: str,
    account_id: str,
    stats_block_id: str | None,
    tasks: list[TrackedTask],
) -> None:
    session.add(PublishedRoadmap(page_id=page_id, account_id=account_id, stats_block_id=stats_block_id))
    for task in tasks:
        session.add(
            PublishedRoadmapTask(
                page_id=page_id,
                task_id=task.task_id,
                title=task.title,
                checkbox_block_id=task.checkbox_block_id,
            )
        )
    session.commit()


def get_published_roadmap(session: Session, page_id: str) -> PublishedRoadmapRecord | None:
    roadmap = session.get(PublishedRoadmap, page_id)
    if roadmap is None:
        return None

    rows = session.query(PublishedRoadmapTask).filter_by(page_id=page_id).all()
    tasks = [TrackedTask(t.task_id, t.title, t.checkbox_block_id) for t in rows]
    return PublishedRoadmapRecord(
        page_id=roadmap.page_id,
        account_id=roadmap.account_id,
        stats_block_id=roadmap.stats_block_id,
        tasks=tasks,
    )
