"""create official law document tables

Revision ID: 0004_official_law_docs
Revises: 0003_create_law_update_events
Create Date: 2026-07-09 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0004_official_law_docs"
down_revision: Union[str, Sequence[str], None] = "0003_create_law_update_events"
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
    if not _table_exists("official_law_documents"):
        op.create_table(
            "official_law_documents",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("source_provider", sa.String(length=100), nullable=False),
            sa.Column("source_mode", sa.String(length=50), nullable=False),
            sa.Column("law_title", sa.String(length=255), nullable=False),
            sa.Column("law_short_title", sa.String(length=255), nullable=True),
            sa.Column("law_id", sa.String(length=100), nullable=True),
            sa.Column("mst", sa.String(length=100), nullable=True),
            sa.Column("promulgation_date", sa.Date(), nullable=True),
            sa.Column("enforcement_date", sa.Date(), nullable=True),
            sa.Column("is_current", sa.Boolean(), nullable=True),
            sa.Column("document_status", sa.String(length=100), nullable=False),
            sa.Column("normalized_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("provider_reason", sa.Text(), nullable=True),
            sa.Column("sanitized_source_url", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "source_provider",
                "law_id",
                "mst",
                "enforcement_date",
                name="uq_official_law_documents_provider_law_mst_enforcement",
            ),
        )
    for index_name, columns in {
        "ix_official_law_documents_id": ["id"],
        "ix_official_law_documents_law_title": ["law_title"],
        "ix_official_law_documents_law_id": ["law_id"],
        "ix_official_law_documents_mst": ["mst"],
        "ix_official_law_documents_enforcement_date": ["enforcement_date"],
        "ix_official_law_documents_is_current": ["is_current"],
        "ix_official_law_documents_document_status": ["document_status"],
    }.items():
        if not _index_exists("official_law_documents", index_name):
            op.create_index(index_name, "official_law_documents", columns)

    if not _table_exists("official_law_articles"):
        op.create_table(
            "official_law_articles",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("document_id", sa.Integer(), nullable=False),
            sa.Column("article_no", sa.String(length=100), nullable=False),
            sa.Column("article_title", sa.String(length=255), nullable=True),
            sa.Column("article_text", sa.Text(), nullable=False),
            sa.Column("paragraphs_json", sa.JSON(), nullable=True),
            sa.Column("source_anchor", sa.String(length=255), nullable=True),
            sa.Column("source_hint", sa.Text(), nullable=True),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["document_id"], ["official_law_documents.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
    for index_name, columns in {
        "ix_official_law_articles_id": ["id"],
        "ix_official_law_articles_document_id": ["document_id"],
        "ix_official_law_articles_article_no": ["article_no"],
    }.items():
        if not _index_exists("official_law_articles", index_name):
            op.create_index(index_name, "official_law_articles", columns)

    if not _table_exists("official_law_ingest_runs"):
        op.create_table(
            "official_law_ingest_runs",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("run_type", sa.String(length=100), nullable=False),
            sa.Column("source_mode", sa.String(length=50), nullable=False),
            sa.Column("query", sa.String(length=255), nullable=True),
            sa.Column("status", sa.String(length=100), nullable=False),
            sa.Column("selected_law_title", sa.String(length=255), nullable=True),
            sa.Column("selected_law_id", sa.String(length=100), nullable=True),
            sa.Column("selected_mst", sa.String(length=100), nullable=True),
            sa.Column("candidate_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("article_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("error_reason", sa.Text(), nullable=True),
            sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
    for index_name, columns in {
        "ix_official_law_ingest_runs_id": ["id"],
        "ix_official_law_ingest_runs_status": ["status"],
        "ix_official_law_ingest_runs_query": ["query"],
        "ix_official_law_ingest_runs_source_mode": ["source_mode"],
        "ix_official_law_ingest_runs_started_at": ["started_at"],
    }.items():
        if not _index_exists("official_law_ingest_runs", index_name):
            op.create_index(index_name, "official_law_ingest_runs", columns)

    if not _table_exists("official_law_source_evidence"):
        op.create_table(
            "official_law_source_evidence",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("ingest_run_id", sa.Integer(), nullable=False),
            sa.Column("evidence_type", sa.String(length=100), nullable=False),
            sa.Column("sanitized_summary_json", sa.JSON(), nullable=True),
            sa.Column("raw_available", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("redaction_applied", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["ingest_run_id"], ["official_law_ingest_runs.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
    for index_name, columns in {
        "ix_official_law_source_evidence_id": ["id"],
        "ix_official_law_source_evidence_ingest_run_id": ["ingest_run_id"],
        "ix_official_law_source_evidence_evidence_type": ["evidence_type"],
    }.items():
        if not _index_exists("official_law_source_evidence", index_name):
            op.create_index(index_name, "official_law_source_evidence", columns)


def downgrade() -> None:
    for table_name in [
        "official_law_source_evidence",
        "official_law_articles",
        "official_law_ingest_runs",
        "official_law_documents",
    ]:
        if _table_exists(table_name):
            op.drop_table(table_name)
