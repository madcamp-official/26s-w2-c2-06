"""Notion OAuth 연결 + 발행한 로드맵 추적 ORM 모델."""

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String
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


class PublishedRoadmap(Base):
    """발행된 로드맵 페이지 1개. "새로고침" 시 어떤 계정 토큰으로, 어떤 요약 블록을 갱신할지 안다."""

    __tablename__ = "published_roadmaps"

    page_id: Mapped[str] = mapped_column(String, primary_key=True)
    account_id: Mapped[str] = mapped_column(String, nullable=False)
    stats_block_id: Mapped[str | None] = mapped_column(String, nullable=True)
    published_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class PublishedRoadmapTask(Base):
    """발행된 로드맵 안의 task 1개 — 체크박스 블록 ID를 기억해뒀다가 완료 여부를 다시 읽어온다."""

    __tablename__ = "published_roadmap_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    page_id: Mapped[str] = mapped_column(ForeignKey("published_roadmaps.page_id"), nullable=False)
    task_id: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    checkbox_block_id: Mapped[str] = mapped_column(String, nullable=False)
