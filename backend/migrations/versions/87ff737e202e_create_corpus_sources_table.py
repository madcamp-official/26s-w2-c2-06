"""create corpus_sources table

Revision ID: 87ff737e202e
Revises: 
Create Date: 2026-07-11 16:16:04.971709

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '87ff737e202e'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


corpus_sources = sa.table(
    "corpus_sources",
    sa.column("id", sa.Text),
    sa.column("title", sa.Text),
    sa.column("publisher", sa.Text),
)

# title/publisher만 확인된 값으로 채움 (doc_001/doc_003은 schemas/bp_matching.py의
# DUMMY_MATCH_RESULT에 등장하는 실제 값). industry_tags/published_at/source_url은
# 아직 확정되지 않아 NULL로 비워두고, 확인되는 대로 UPDATE 마이그레이션 추가할 것.
SEED_ROWS = [
    {"id": "doc_001", "title": "SK AX 리포트", "publisher": "SK AX"},
    {"id": "doc_002", "title": "kt cloud AX 트렌드 리포트", "publisher": "kt cloud"},
    {"id": "doc_003", "title": "Wrtn Technologies AX Report", "publisher": "Wrtn"},
    {"id": "doc_004", "title": "원티드 AX 리포트", "publisher": "원티드"},
]


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "corpus_sources",
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("publisher", sa.Text, nullable=False),
        sa.Column("industry_tags", sa.ARRAY(sa.Text), nullable=True),
        sa.Column("published_at", sa.Date, nullable=True),
        sa.Column("source_url", sa.Text, nullable=True),
        sa.Column(
            "ingested_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.bulk_insert(corpus_sources, SEED_ROWS)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("corpus_sources")
