"""add attached table evidence support
Revision ID: 0011_phase48_attached_tables
Revises: 0010_phase44_scheduler
"""
from alembic import op
import sqlalchemy as sa

revision = "0011_phase48_attached_tables"
down_revision = "0010_phase44_scheduler"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "law_attached_table_evidence",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("law_id", sa.Integer(), sa.ForeignKey("laws.id", ondelete="CASCADE"), nullable=False),
        sa.Column("table_key", sa.String(200), nullable=False),
        sa.Column("table_number", sa.String(50), nullable=False),
        sa.Column("table_title", sa.String(500), nullable=False),
        sa.Column("mst", sa.String(100), nullable=False),
        sa.Column("effective_date", sa.Date()),
        sa.Column("normalized_text", sa.Text(), nullable=False),
        sa.Column("source", sa.String(100), nullable=False, server_default="MOLEG_LIVE"),
        sa.Column("provenance_json", sa.JSON(), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("law_id", "table_key", "mst", name="uq_law_attached_table_evidence_version"),
    )
    op.create_index("ix_law_attached_table_evidence_as_of", "law_attached_table_evidence", ["law_id", "effective_date"])


def downgrade():
    op.drop_index("ix_law_attached_table_evidence_as_of", table_name="law_attached_table_evidence")
    op.drop_table("law_attached_table_evidence")
