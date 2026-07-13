"""create notion_connections table

Revision ID: 827eac101fce
Revises: 
Create Date: 2026-07-13 10:51:57.588739

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '827eac101fce'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "notion_connections",
        sa.Column("account_id", sa.Text, primary_key=True),
        sa.Column("access_token", sa.Text, nullable=False),
        sa.Column("refresh_token", sa.Text, nullable=True),
        sa.Column("workspace_id", sa.Text, nullable=False),
        sa.Column("workspace_name", sa.Text, nullable=True),
        sa.Column("bot_id", sa.Text, nullable=False),
        sa.Column("default_page_id", sa.Text, nullable=True),
        sa.Column(
            "connected_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("notion_connections")
