"""QA_amendments 2절: 발견/적용 수 콜아웃 -> 목표 콜아웃 1개로 교체 + AX 성숙도 진단 DB 추적 컬럼 추가

Revision ID: a3f0c9d21b44
Revises: 0ec190c0cfac
Create Date: 2026-07-15 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a3f0c9d21b44'
down_revision: Union[str, Sequence[str], None] = '0ec190c0cfac'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_column("notion_workspaces", "discovered_count_block_id")
    op.drop_column("notion_workspaces", "applied_count_block_id")
    op.add_column("notion_workspaces", sa.Column("goal_callout_block_id", sa.Text, nullable=True))
    op.add_column("notion_workspaces", sa.Column("maturity_database_id", sa.Text, nullable=True))
    op.add_column("notion_workspaces", sa.Column("maturity_data_source_id", sa.Text, nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("notion_workspaces", "maturity_data_source_id")
    op.drop_column("notion_workspaces", "maturity_database_id")
    op.drop_column("notion_workspaces", "goal_callout_block_id")
    op.add_column("notion_workspaces", sa.Column("applied_count_block_id", sa.Text, nullable=True))
    op.add_column("notion_workspaces", sa.Column("discovered_count_block_id", sa.Text, nullable=True))
