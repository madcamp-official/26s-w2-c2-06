"""Notion OAuth 연결 + 발행한 데이터베이스/행 추적 ORM 모델.

v0.9(9절)에서 "페이지+체크박스" 방식을 "Opportunity Map/Roadmap/팀원 데이터베이스" 방식으로
재설계하면서 `PublishedRoadmap`/`PublishedRoadmapTask`(체크박스 블록 ID 추적)를 걷어내고
아래 4개 테이블로 교체했다. Notion 쪽에 "이 값으로 조회"할 방법이 마땅치 않은 조합(계정별
데이터베이스 ID, work_item_id/task_id/member_id별 페이지 ID)이라 전부 우리 쪽에서 기억한다.

QA_amendments 2절 반영(2026-07-15): 발견/적용 수 콜아웃 2개(discovered/applied_count_block_id)를
없애고 목표 콜아웃 1개(goal_callout_block_id)로 교체 — 재발행마다 목표 문구를 최신으로 갱신한다.
"AX 성숙도 진단" DB(maturity_*)는 진단이 있을 때만 최초 1회 지연 생성되므로 nullable이다."""

from datetime import datetime, timezone

from sqlalchemy import DateTime, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class NotionConnection(Base):
    __tablename__ = "notion_connections"

    account_id: Mapped[str] = mapped_column(String, primary_key=True)
    access_token: Mapped[str] = mapped_column(String, nullable=False)
    refresh_token: Mapped[str | None] = mapped_column(String, nullable=True)
    workspace_id: Mapped[str] = mapped_column(String, nullable=False)
    workspace_name: Mapped[str | None] = mapped_column(String, nullable=True)
    bot_id: Mapped[str] = mapped_column(String, nullable=False)
    default_page_id: Mapped[str | None] = mapped_column(String, nullable=True)
    connected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class NotionWorkspace(Base):
    """계정 1개당 발행 대상 데이터베이스 3종 + 대시보드 페이지 + 대시보드 콜아웃 블록 ID.
    최초 발행 시 1회 생성하고, 이후 재발행은 이 레코드를 재사용해 데이터베이스를 중복 생성하지 않는다."""

    __tablename__ = "notion_workspaces"

    account_id: Mapped[str] = mapped_column(String, primary_key=True)
    team_database_id: Mapped[str] = mapped_column(String, nullable=False)
    team_data_source_id: Mapped[str] = mapped_column(String, nullable=False)
    opportunity_database_id: Mapped[str] = mapped_column(String, nullable=False)
    opportunity_data_source_id: Mapped[str] = mapped_column(String, nullable=False)
    roadmap_database_id: Mapped[str] = mapped_column(String, nullable=False)
    roadmap_data_source_id: Mapped[str] = mapped_column(String, nullable=False)
    dashboard_page_id: Mapped[str] = mapped_column(String, nullable=False)
    dashboard_url: Mapped[str] = mapped_column(String, nullable=False)
    goal_callout_block_id: Mapped[str | None] = mapped_column(String, nullable=True)
    maturity_database_id: Mapped[str | None] = mapped_column(String, nullable=True)
    maturity_data_source_id: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class NotionMemberPage(Base):
    """팀원 DB 행 1개. member_id(온보딩 익명 ID)는 계정 안에서 계속 재사용된다(goal 단위 아님)."""

    __tablename__ = "notion_member_pages"
    __table_args__ = (UniqueConstraint("account_id", "member_id"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    account_id: Mapped[str] = mapped_column(String, nullable=False)
    member_id: Mapped[str] = mapped_column(String, nullable=False)
    page_id: Mapped[str] = mapped_column(String, nullable=False)


class NotionWorkItemPage(Base):
    """Opportunity Map DB 행 1개 (work_item_id는 goal_id 안에서만 유일)."""

    __tablename__ = "notion_work_item_pages"
    __table_args__ = (UniqueConstraint("account_id", "goal_id", "work_item_id"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    account_id: Mapped[str] = mapped_column(String, nullable=False)
    goal_id: Mapped[str] = mapped_column(String, nullable=False)
    work_item_id: Mapped[str] = mapped_column(String, nullable=False)
    page_id: Mapped[str] = mapped_column(String, nullable=False)


class NotionTaskPage(Base):
    """Roadmap DB 행 1개 (task_id는 goal_id 안에서만 유일)."""

    __tablename__ = "notion_task_pages"
    __table_args__ = (UniqueConstraint("account_id", "goal_id", "task_id"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    account_id: Mapped[str] = mapped_column(String, nullable=False)
    goal_id: Mapped[str] = mapped_column(String, nullable=False)
    task_id: Mapped[str] = mapped_column(String, nullable=False)
    page_id: Mapped[str] = mapped_column(String, nullable=False)
