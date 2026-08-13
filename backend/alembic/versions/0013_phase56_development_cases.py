"""phase 56 development cases

Revision ID: 0013_phase56_development_cases
Revises: 0012_phase51_pgvector
"""
from alembic import op
import sqlalchemy as sa


revision = "0013_phase56_development_cases"
down_revision = "0012_phase51_pgvector"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "development_cases",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("location", sa.String(500), nullable=True),
        sa.Column("area_m2", sa.Float(), nullable=True),
        sa.Column("method", sa.String(255), nullable=True),
        sa.Column("operator_type", sa.String(255), nullable=True),
        sa.Column("timeline", sa.JSON(), nullable=False),
        sa.Column("history", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_development_cases_id", "development_cases", ["id"])
    op.create_index("ix_development_cases_name", "development_cases", ["name"])


def downgrade():
    op.drop_index("ix_development_cases_name", table_name="development_cases")
    op.drop_index("ix_development_cases_id", table_name="development_cases")
    op.drop_table("development_cases")
