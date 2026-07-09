"""add procedure candidate confirmation metadata

Revision ID: 0006_candidate_confirmation
Revises: 0005_proc_article_candidates
Create Date: 2026-07-09 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0006_candidate_confirmation"
down_revision: Union[str, Sequence[str], None] = "0005_proc_article_candidates"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def _index_exists(table_name: str, index_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not _table_exists(table_name):
        return False
    return any(index["name"] == index_name for index in inspector.get_indexes(table_name))


def upgrade() -> None:
    if not _table_exists("procedure_official_article_candidates"):
        return
    op.execute("ALTER TABLE procedure_official_article_candidates ADD COLUMN IF NOT EXISTS confirmed_at TIMESTAMP WITH TIME ZONE")
    op.execute("ALTER TABLE procedure_official_article_candidates ADD COLUMN IF NOT EXISTS confirmed_by VARCHAR(255)")
    op.execute("ALTER TABLE procedure_official_article_candidates ADD COLUMN IF NOT EXISTS confirmed_source VARCHAR(100)")
    op.execute("ALTER TABLE procedure_official_article_candidates ADD COLUMN IF NOT EXISTS confirmation_note TEXT")
    if not _index_exists("procedure_official_article_candidates", "ix_proc_article_candidates_is_confirmed"):
        op.create_index("ix_proc_article_candidates_is_confirmed", "procedure_official_article_candidates", ["is_confirmed"])
    if not _index_exists("procedure_official_article_candidates", "ix_proc_article_candidates_confirmed_at"):
        op.create_index("ix_proc_article_candidates_confirmed_at", "procedure_official_article_candidates", ["confirmed_at"])


def downgrade() -> None:
    if not _table_exists("procedure_official_article_candidates"):
        return
    if _index_exists("procedure_official_article_candidates", "ix_proc_article_candidates_confirmed_at"):
        op.drop_index("ix_proc_article_candidates_confirmed_at", table_name="procedure_official_article_candidates")
    if _index_exists("procedure_official_article_candidates", "ix_proc_article_candidates_is_confirmed"):
        op.drop_index("ix_proc_article_candidates_is_confirmed", table_name="procedure_official_article_candidates")
    op.execute("ALTER TABLE procedure_official_article_candidates DROP COLUMN IF EXISTS confirmation_note")
    op.execute("ALTER TABLE procedure_official_article_candidates DROP COLUMN IF EXISTS confirmed_source")
    op.execute("ALTER TABLE procedure_official_article_candidates DROP COLUMN IF EXISTS confirmed_by")
    op.execute("ALTER TABLE procedure_official_article_candidates DROP COLUMN IF EXISTS confirmed_at")
