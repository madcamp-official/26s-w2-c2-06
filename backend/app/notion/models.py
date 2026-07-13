"""Notion OAuth 연결 정보 ORM 모델. 계정(account_id)당 1개의 연결을 저장한다."""

from datetime import datetime, timezone

from sqlalchemy import DateTime, String
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
