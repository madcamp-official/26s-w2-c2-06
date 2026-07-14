"""계정별로 발행한 Notion 데이터베이스/행 ID를 저장·조회한다.

`sync.py`가 이 모듈로 "이미 데이터베이스가 있으면 재사용, 행이 있으면 갱신·없으면 생성"을
판단한다. Notion 쪽에 이 조합(work_item_id/task_id/member_id별 페이지)을 조회할 마땅한 API가
없어서 전부 우리 쪽 Postgres가 정본이다."""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.notion.models import NotionMemberPage, NotionTaskPage, NotionWorkItemPage, NotionWorkspace


@dataclass
class WorkspaceRecord:
    account_id: str
    team_database_id: str
    team_data_source_id: str
    opportunity_database_id: str
    opportunity_data_source_id: str
    roadmap_database_id: str
    roadmap_data_source_id: str
    dashboard_page_id: str
    dashboard_url: str
    discovered_count_block_id: str | None
    applied_count_block_id: str | None


def get_workspace(session: Session, account_id: str) -> WorkspaceRecord | None:
    row = session.get(NotionWorkspace, account_id)
    if row is None:
        return None
    return WorkspaceRecord(
        account_id=row.account_id,
        team_database_id=row.team_database_id,
        team_data_source_id=row.team_data_source_id,
        opportunity_database_id=row.opportunity_database_id,
        opportunity_data_source_id=row.opportunity_data_source_id,
        roadmap_database_id=row.roadmap_database_id,
        roadmap_data_source_id=row.roadmap_data_source_id,
        dashboard_page_id=row.dashboard_page_id,
        dashboard_url=row.dashboard_url,
        discovered_count_block_id=row.discovered_count_block_id,
        applied_count_block_id=row.applied_count_block_id,
    )


def save_workspace(session: Session, record: WorkspaceRecord) -> None:
    existing = session.get(NotionWorkspace, record.account_id)
    if existing is None:
        session.add(NotionWorkspace(**record.__dict__))
    else:
        for field, value in record.__dict__.items():
            setattr(existing, field, value)
    session.commit()


def update_dashboard_stat_blocks(
    session: Session, account_id: str, discovered_block_id: str, applied_block_id: str
) -> None:
    workspace = session.get(NotionWorkspace, account_id)
    if workspace is None:
        return
    workspace.discovered_count_block_id = discovered_block_id
    workspace.applied_count_block_id = applied_block_id
    session.commit()


def get_member_page_id(session: Session, account_id: str, member_id: str) -> str | None:
    row = (
        session.query(NotionMemberPage)
        .filter_by(account_id=account_id, member_id=member_id)
        .one_or_none()
    )
    return row.page_id if row else None


def save_member_page(session: Session, account_id: str, member_id: str, page_id: str) -> None:
    session.add(NotionMemberPage(account_id=account_id, member_id=member_id, page_id=page_id))
    session.commit()


def get_work_item_page_id(
    session: Session, account_id: str, goal_id: str, work_item_id: str
) -> str | None:
    row = (
        session.query(NotionWorkItemPage)
        .filter_by(account_id=account_id, goal_id=goal_id, work_item_id=work_item_id)
        .one_or_none()
    )
    return row.page_id if row else None


def save_work_item_page(
    session: Session, account_id: str, goal_id: str, work_item_id: str, page_id: str
) -> None:
    session.add(
        NotionWorkItemPage(
            account_id=account_id, goal_id=goal_id, work_item_id=work_item_id, page_id=page_id
        )
    )
    session.commit()


def get_task_page_id(session: Session, account_id: str, goal_id: str, task_id: str) -> str | None:
    row = (
        session.query(NotionTaskPage)
        .filter_by(account_id=account_id, goal_id=goal_id, task_id=task_id)
        .one_or_none()
    )
    return row.page_id if row else None


def save_task_page(
    session: Session, account_id: str, goal_id: str, task_id: str, page_id: str
) -> None:
    session.add(
        NotionTaskPage(account_id=account_id, goal_id=goal_id, task_id=task_id, page_id=page_id)
    )
    session.commit()
