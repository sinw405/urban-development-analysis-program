"""create project and analysis result tables

Revision ID: 0001_create_project_analysis
Revises:
Create Date: 2026-07-06 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001_create_project_analysis"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def _index_exists(table_name: str, index_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return any(index["name"] == index_name for index in inspector.get_indexes(table_name))


def upgrade() -> None:
    if not _table_exists("projects"):
        op.create_table(
            "projects",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("project_name", sa.String(length=255), nullable=False),
            sa.Column("location", sa.String(length=500), nullable=False),
            sa.Column("area_square_meters", sa.Float(), nullable=False),
            sa.Column("implementation_method", sa.String(length=255), nullable=False),
            sa.Column("implementer_type", sa.String(length=255), nullable=False),
            sa.Column("local_government", sa.String(length=255), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.CheckConstraint("area_square_meters > 0", name="ck_projects_area_square_meters_positive"),
            sa.PrimaryKeyConstraint("id"),
        )

    if not _index_exists("projects", "ix_projects_project_name"):
        op.create_index("ix_projects_project_name", "projects", ["project_name"])
    if not _index_exists("projects", "ix_projects_local_government"):
        op.create_index("ix_projects_local_government", "projects", ["local_government"])
    if not _index_exists("projects", "ix_projects_created_at"):
        op.create_index("ix_projects_created_at", "projects", ["created_at"])

    if not _table_exists("analysis_results"):
        op.create_table(
            "analysis_results",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("project_id", sa.Integer(), nullable=False),
            sa.Column("request_payload", sa.JSON(), nullable=False),
            sa.Column("result_payload", sa.JSON(), nullable=False),
            sa.Column("rule_version", sa.String(length=50), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
            sa.PrimaryKeyConstraint("id"),
        )

    if not _index_exists("analysis_results", "ix_analysis_results_project_id"):
        op.create_index("ix_analysis_results_project_id", "analysis_results", ["project_id"])
    if not _index_exists("analysis_results", "ix_analysis_results_created_at"):
        op.create_index("ix_analysis_results_created_at", "analysis_results", ["created_at"])


def downgrade() -> None:
    if _table_exists("analysis_results"):
        op.drop_table("analysis_results")
    if _table_exists("projects"):
        op.drop_table("projects")
