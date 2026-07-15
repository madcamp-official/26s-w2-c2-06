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
    goal_callout_block_id: str | None
    maturity_database_id: str | None = None
    maturity_data_source_id: str | None = None


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
        goal_callout_block_id=row.goal_callout_block_id,
        maturity_database_id=row.maturity_database_id,
        maturity_data_source_id=row.maturity_data_source_id,
    )


def save_workspace(session: Session, record: WorkspaceRecord) -> None:
    existing = session.get(NotionWorkspace, record.account_id)
    if existing is None:
        session.add(NotionWorkspace(**record.__dict__))
    else:
        for field, value in record.__dict__.items():
            setattr(existing, field, value)
    session.commit()


def forget_workspace(session: Session, account_id: str) -> None:
    """저장된 워크스페이스·행 매핑을 전부 지운다 — 대시보드 페이지가 Notion에서 지워지거나
    휴지통에 들어가 더 이상 못 쓰게 됐을 때, 다음 발행이 처음부터 새로 만들도록 한다
    (테스트/정리 중 대시보드 페이지가 삭제되는 사고가 실 운영에서 반복됐다, 2026-07-15).
    지워진 워크스페이스의 옛 database_id를 가리키는 행 매핑도 같이 지워야, 새 워크스페이스의
    새 데이터베이스에 옛 페이지 ID로 잘못 업데이트를 시도하지 않는다."""
    session.query(NotionMemberPage).filter_by(account_id=account_id).delete()
    session.query(NotionWorkItemPage).filter_by(account_id=account_id).delete()
    session.query(NotionTaskPage).filter_by(account_id=account_id).delete()
    session.query(NotionWorkspace).filter_by(account_id=account_id).delete()
    session.commit()


def save_maturity_database(
    session: Session, account_id: str, database_id: str, data_source_id: str
) -> None:
    """"AX 성숙도 진단" DB는 첫 진단 발행 시점에만 지연 생성되므로, 워크스페이스 최초 생성 이후
    별도로 ID를 채워 넣는다(sync.sync_diagnosis 참고)."""
    workspace = session.get(NotionWorkspace, account_id)
    if workspace is None:
        return
    workspace.maturity_database_id = database_id
    workspace.maturity_data_source_id = data_source_id
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
