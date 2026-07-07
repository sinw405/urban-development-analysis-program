"""create legal reference tables

Revision ID: 0002_create_legal_refs
Revises: 0001_create_project_analysis
Create Date: 2026-07-07 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002_create_legal_refs"
down_revision: Union[str, Sequence[str], None] = "0001_create_project_analysis"
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
    if not _table_exists("laws"):
        op.create_table(
            "laws",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("law_name", sa.String(length=255), nullable=False),
            sa.Column("law_key", sa.String(length=100), nullable=True),
            sa.Column("source", sa.String(length=100), nullable=False),
            sa.Column("mapping_status", sa.String(length=100), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
    if not _index_exists("laws", "ix_laws_id"):
        op.create_index("ix_laws_id", "laws", ["id"])
    if not _index_exists("laws", "ix_laws_law_name"):
        op.create_index("ix_laws_law_name", "laws", ["law_name"])
    if not _index_exists("laws", "ix_laws_mapping_status"):
        op.create_index("ix_laws_mapping_status", "laws", ["mapping_status"])

    if not _table_exists("law_articles"):
        op.create_table(
            "law_articles",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("law_id", sa.Integer(), nullable=False),
            sa.Column("article_key", sa.String(length=100), nullable=True),
            sa.Column("article_number_text", sa.String(length=100), nullable=True),
            sa.Column("article_title", sa.String(length=255), nullable=True),
            sa.Column("mapping_status", sa.String(length=100), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["law_id"], ["laws.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
    if not _index_exists("law_articles", "ix_law_articles_id"):
        op.create_index("ix_law_articles_id", "law_articles", ["id"])
    if not _index_exists("law_articles", "ix_law_articles_law_id"):
        op.create_index("ix_law_articles_law_id", "law_articles", ["law_id"])
    if not _index_exists("law_articles", "ix_law_articles_mapping_status"):
        op.create_index("ix_law_articles_mapping_status", "law_articles", ["mapping_status"])

    if not _table_exists("law_article_versions"):
        op.create_table(
            "law_article_versions",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("law_article_id", sa.Integer(), nullable=False),
            sa.Column("effective_date", sa.Date(), nullable=True),
            sa.Column("article_text", sa.Text(), nullable=True),
            sa.Column("raw_payload_json", sa.JSON(), nullable=True),
            sa.Column("source", sa.String(length=100), nullable=False),
            sa.Column("version_status", sa.String(length=100), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["law_article_id"], ["law_articles.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
    if not _index_exists("law_article_versions", "ix_law_article_versions_id"):
        op.create_index("ix_law_article_versions_id", "law_article_versions", ["id"])
    if not _index_exists("law_article_versions", "ix_law_article_versions_law_article_id"):
        op.create_index("ix_law_article_versions_law_article_id", "law_article_versions", ["law_article_id"])
    if not _index_exists("law_article_versions", "ix_law_article_versions_version_status"):
        op.create_index("ix_law_article_versions_version_status", "law_article_versions", ["version_status"])

    if not _table_exists("procedure_legal_references"):
        op.create_table(
            "procedure_legal_references",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("step_code", sa.String(length=100), nullable=False),
            sa.Column("law_id", sa.Integer(), nullable=True),
            sa.Column("law_article_id", sa.Integer(), nullable=True),
            sa.Column("reference_status", sa.String(length=100), nullable=False),
            sa.Column("placeholder", sa.String(length=255), nullable=False),
            sa.Column("notes_json", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["law_article_id"], ["law_articles.id"]),
            sa.ForeignKeyConstraint(["law_id"], ["laws.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
    if not _index_exists("procedure_legal_references", "ix_procedure_legal_references_id"):
        op.create_index("ix_procedure_legal_references_id", "procedure_legal_references", ["id"])
    if not _index_exists("procedure_legal_references", "ix_procedure_legal_references_step_code"):
        op.create_index("ix_procedure_legal_references_step_code", "procedure_legal_references", ["step_code"])
    if not _index_exists("procedure_legal_references", "ix_procedure_legal_references_reference_status"):
        op.create_index("ix_procedure_legal_references_reference_status", "procedure_legal_references", ["reference_status"])


def downgrade() -> None:
    if _table_exists("procedure_legal_references"):
        op.drop_table("procedure_legal_references")
    if _table_exists("law_article_versions"):
        op.drop_table("law_article_versions")
    if _table_exists("law_articles"):
        op.drop_table("law_articles")
    if _table_exists("laws"):
        op.drop_table("laws")
