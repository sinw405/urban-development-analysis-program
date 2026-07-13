"""add law change impact and review event tables

Revision ID: 0007_law_change_impact
Revises: 0006_candidate_confirmation
Create Date: 2026-07-14 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0007_law_change_impact"
down_revision: Union[str, Sequence[str], None] = "0006_candidate_confirmation"
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
    if not _table_exists("procedure_article_review_events"):
        op.create_table(
            "procedure_article_review_events",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("candidate_id", sa.Integer(), nullable=False),
            sa.Column("previous_status", sa.String(length=100), nullable=False),
            sa.Column("new_status", sa.String(length=100), nullable=False),
            sa.Column("reviewer", sa.String(length=255), nullable=False),
            sa.Column("review_note", sa.Text(), nullable=False),
            sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("reviewed_mst", sa.String(length=100), nullable=True),
            sa.Column("reviewed_effective_date", sa.Date(), nullable=True),
            sa.Column("source", sa.String(length=100), nullable=False),
            sa.Column("metadata_json", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["candidate_id"], ["procedure_official_article_candidates.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
    for index_name, columns in {
        "ix_proc_article_review_events_candidate_id": ["candidate_id"],
        "ix_proc_article_review_events_reviewed_at": ["reviewed_at"],
        "ix_proc_article_review_events_new_status": ["new_status"],
    }.items():
        if not _index_exists("procedure_article_review_events", index_name):
            op.create_index(index_name, "procedure_article_review_events", columns)

    if not _table_exists("law_change_impact_events"):
        op.create_table(
            "law_change_impact_events",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("idempotency_key", sa.String(length=255), nullable=False),
            sa.Column("law_name", sa.String(length=255), nullable=False),
            sa.Column("law_id", sa.String(length=100), nullable=True),
            sa.Column("from_mst", sa.String(length=100), nullable=False),
            sa.Column("to_mst", sa.String(length=100), nullable=False),
            sa.Column("from_effective_date", sa.Date(), nullable=True),
            sa.Column("to_effective_date", sa.Date(), nullable=True),
            sa.Column("article_stable_id", sa.String(length=255), nullable=False),
            sa.Column("article_no", sa.String(length=100), nullable=False),
            sa.Column("article_title", sa.String(length=255), nullable=True),
            sa.Column("change_type", sa.String(length=50), nullable=False),
            sa.Column("previous_content_hash", sa.String(length=64), nullable=True),
            sa.Column("current_content_hash", sa.String(length=64), nullable=True),
            sa.Column("affected_procedure_code", sa.String(length=100), nullable=True),
            sa.Column("affected_procedure_name", sa.String(length=255), nullable=True),
            sa.Column("candidate_id", sa.Integer(), nullable=True),
            sa.Column("mapping_id", sa.Integer(), nullable=True),
            sa.Column("mapping_status", sa.String(length=100), nullable=False),
            sa.Column("previous_mapping_status", sa.String(length=100), nullable=True),
            sa.Column("derived_review_status", sa.String(length=100), nullable=False),
            sa.Column("impact_level", sa.String(length=50), nullable=False),
            sa.Column("impact_reason", sa.Text(), nullable=False),
            sa.Column("source_provenance", sa.JSON(), nullable=True),
            sa.Column("official_url", sa.Text(), nullable=True),
            sa.Column("official_url_status", sa.String(length=50), nullable=False, server_default="unavailable"),
            sa.Column("detected_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("status", sa.String(length=100), nullable=False, server_default="pending_review"),
            sa.Column("metadata_json", sa.JSON(), nullable=True),
            sa.ForeignKeyConstraint(["candidate_id"], ["procedure_official_article_candidates.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("idempotency_key", name="uq_law_change_impact_events_idempotency_key"),
        )
    for index_name, columns in {
        "ix_law_change_impact_events_law_id": ["law_id"],
        "ix_law_change_impact_events_to_mst": ["to_mst"],
        "ix_law_change_impact_events_change_type": ["change_type"],
        "ix_law_change_impact_events_impact_level": ["impact_level"],
        "ix_law_change_impact_events_review_status": ["derived_review_status"],
        "ix_law_change_impact_events_detected_at": ["detected_at"],
    }.items():
        if not _index_exists("law_change_impact_events", index_name):
            op.create_index(index_name, "law_change_impact_events", columns)


def downgrade() -> None:
    if _table_exists("law_change_impact_events"):
        op.drop_table("law_change_impact_events")
    if _table_exists("procedure_article_review_events"):
        op.drop_table("procedure_article_review_events")
