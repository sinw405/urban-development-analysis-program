"""create law update events

Revision ID: 0003_create_law_update_events
Revises: 0002_create_legal_refs
Create Date: 2026-07-07 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0003_create_law_update_events"
down_revision: Union[str, Sequence[str], None] = "0002_create_legal_refs"
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
    if not _table_exists("law_update_events"):
        op.create_table(
            "law_update_events",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("law_id", sa.Integer(), nullable=False),
            sa.Column("article_id", sa.Integer(), nullable=False),
            sa.Column("previous_version_id", sa.Integer(), nullable=True),
            sa.Column("new_version_id", sa.Integer(), nullable=True),
            sa.Column("change_type", sa.String(length=100), nullable=False),
            sa.Column("detected_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("effective_date", sa.Date(), nullable=True),
            sa.Column("status", sa.String(length=100), nullable=False),
            sa.Column("source", sa.String(length=100), nullable=False),
            sa.Column("metadata_json", sa.JSON(), nullable=True),
            sa.ForeignKeyConstraint(["article_id"], ["law_articles.id"]),
            sa.ForeignKeyConstraint(["law_id"], ["laws.id"]),
            sa.ForeignKeyConstraint(["new_version_id"], ["law_article_versions.id"]),
            sa.ForeignKeyConstraint(["previous_version_id"], ["law_article_versions.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
    if not _index_exists("law_update_events", "ix_law_update_events_id"):
        op.create_index("ix_law_update_events_id", "law_update_events", ["id"])
    if not _index_exists("law_update_events", "ix_law_update_events_law_id"):
        op.create_index("ix_law_update_events_law_id", "law_update_events", ["law_id"])
    if not _index_exists("law_update_events", "ix_law_update_events_article_id"):
        op.create_index("ix_law_update_events_article_id", "law_update_events", ["article_id"])
    if not _index_exists("law_update_events", "ix_law_update_events_detected_at"):
        op.create_index("ix_law_update_events_detected_at", "law_update_events", ["detected_at"])
    if not _index_exists("law_update_events", "ix_law_update_events_status"):
        op.create_index("ix_law_update_events_status", "law_update_events", ["status"])


def downgrade() -> None:
    if _table_exists("law_update_events"):
        op.drop_table("law_update_events")
