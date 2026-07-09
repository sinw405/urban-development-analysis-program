"""create procedure official article candidate table

Revision ID: 0005_proc_article_candidates
Revises: 0004_official_law_docs
Create Date: 2026-07-09 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0005_proc_article_candidates"
down_revision: Union[str, Sequence[str], None] = "0004_official_law_docs"
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
        op.create_table(
            "procedure_official_article_candidates",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("procedure_code", sa.String(length=100), nullable=False),
            sa.Column("procedure_name", sa.String(length=255), nullable=True),
            sa.Column("law_title", sa.String(length=255), nullable=False),
            sa.Column("law_short_title", sa.String(length=255), nullable=True),
            sa.Column("law_id", sa.String(length=100), nullable=True),
            sa.Column("mst", sa.String(length=100), nullable=True),
            sa.Column("document_id", sa.Integer(), nullable=True),
            sa.Column("article_id", sa.Integer(), nullable=True),
            sa.Column("article_no", sa.String(length=100), nullable=True),
            sa.Column("article_title", sa.String(length=255), nullable=True),
            sa.Column("article_anchor", sa.String(length=255), nullable=True),
            sa.Column("match_method", sa.String(length=100), nullable=False),
            sa.Column("match_score", sa.Float(), nullable=False, server_default="0"),
            sa.Column("match_status", sa.String(length=100), nullable=False, server_default="candidate"),
            sa.Column("source_mode", sa.String(length=50), nullable=False),
            sa.Column("source_mode_detail", sa.String(length=100), nullable=True),
            sa.Column("confidence_level", sa.String(length=50), nullable=False, server_default="unknown"),
            sa.Column("is_confirmed", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("provider_reason", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["article_id"], ["official_law_articles.id"]),
            sa.ForeignKeyConstraint(["document_id"], ["official_law_documents.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "procedure_code",
                "article_id",
                "match_method",
                "source_mode_detail",
                name="uq_proc_article_candidate_step_article_source",
            ),
        )
    for index_name, columns in {
        "ix_proc_article_candidates_procedure_code": ["procedure_code"],
        "ix_proc_article_candidates_law_title": ["law_title"],
        "ix_proc_article_candidates_law_id": ["law_id"],
        "ix_proc_article_candidates_article_id": ["article_id"],
        "ix_proc_article_candidates_match_status": ["match_status"],
        "ix_proc_article_candidates_source_mode_detail": ["source_mode_detail"],
    }.items():
        if not _index_exists("procedure_official_article_candidates", index_name):
            op.create_index(index_name, "procedure_official_article_candidates", columns)


def downgrade() -> None:
    if _table_exists("procedure_official_article_candidates"):
        op.drop_table("procedure_official_article_candidates")

