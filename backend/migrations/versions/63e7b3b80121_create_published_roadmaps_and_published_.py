"""create published_roadmaps and published_roadmap_tasks tables

Revision ID: 63e7b3b80121
Revises: 827eac101fce
Create Date: 2026-07-13 14:24:59.484528

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '63e7b3b80121'
down_revision: Union[str, Sequence[str], None] = '827eac101fce'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
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


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("published_roadmap_tasks")
    op.drop_table("published_roadmaps")
