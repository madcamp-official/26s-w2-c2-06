"""replace checkbox tracking with notion database sync tables

Revision ID: 0ec190c0cfac
Revises: 63e7b3b80121
Create Date: 2026-07-14 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0ec190c0cfac'
down_revision: Union[str, Sequence[str], None] = '63e7b3b80121'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_table("published_roadmap_tasks")
    op.drop_table("published_roadmaps")

    op.create_table(
        "notion_workspaces",
        sa.Column("account_id", sa.Text, primary_key=True),
        sa.Column("team_database_id", sa.Text, nullable=False),
        sa.Column("team_data_source_id", sa.Text, nullable=False),
        sa.Column("opportunity_database_id", sa.Text, nullable=False),
        sa.Column("opportunity_data_source_id", sa.Text, nullable=False),
        sa.Column("roadmap_database_id", sa.Text, nullable=False),
        sa.Column("roadmap_data_source_id", sa.Text, nullable=False),
        sa.Column("dashboard_page_id", sa.Text, nullable=False),
        sa.Column("dashboard_url", sa.Text, nullable=False),
        sa.Column("discovered_count_block_id", sa.Text, nullable=True),
        sa.Column("applied_count_block_id", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_table(
        "notion_member_pages",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("account_id", sa.Text, nullable=False),
        sa.Column("member_id", sa.Text, nullable=False),
        sa.Column("page_id", sa.Text, nullable=False),
        sa.UniqueConstraint("account_id", "member_id"),
    )

    op.create_table(
        "notion_work_item_pages",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("account_id", sa.Text, nullable=False),
        sa.Column("goal_id", sa.Text, nullable=False),
        sa.Column("work_item_id", sa.Text, nullable=False),
        sa.Column("page_id", sa.Text, nullable=False),
        sa.UniqueConstraint("account_id", "goal_id", "work_item_id"),
    )

    op.create_table(
        "notion_task_pages",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("account_id", sa.Text, nullable=False),
        sa.Column("goal_id", sa.Text, nullable=False),
        sa.Column("task_id", sa.Text, nullable=False),
        sa.Column("page_id", sa.Text, nullable=False),
        sa.UniqueConstraint("account_id", "goal_id", "task_id"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("notion_task_pages")
    op.drop_table("notion_work_item_pages")
    op.drop_table("notion_member_pages")
    op.drop_table("notion_workspaces")

    op.create_table(
        "published_roadmaps",
        sa.Column("page_id", sa.Text, primary_key=True),
        sa.Column("account_id", sa.Text, nullable=False),
        sa.Column("stats_block_id", sa.Text, nullable=True),
        sa.Column(
            "published_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_table(
        "published_roadmap_tasks",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "page_id", sa.Text, sa.ForeignKey("published_roadmaps.page_id"), nullable=False
        ),
        sa.Column("task_id", sa.Text, nullable=False),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("checkbox_block_id", sa.Text, nullable=False),
    )
