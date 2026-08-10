"""add phase43 live law change aggregate events and audits
Revision ID: 0009_phase43_live_events
Revises: 0008_phase40_event_fk_cascade
"""
from alembic import op
import sqlalchemy as sa
revision = "0009_phase43_live_events"
down_revision = "0008_phase40_event_fk_cascade"
branch_labels = None
depends_on = None
def upgrade():
    op.create_table("live_law_change_events",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("source", sa.String(50), nullable=False),
        sa.Column("law_id", sa.String(100)), sa.Column("law_name", sa.String(255), nullable=False),
        sa.Column("from_mst", sa.String(100), nullable=False), sa.Column("to_mst", sa.String(100), nullable=False),
        sa.Column("from_effective_date", sa.Date()), sa.Column("to_effective_date", sa.Date()),
        sa.Column("version_changed", sa.Boolean(), nullable=False), sa.Column("content_changed", sa.Boolean()),
        sa.Column("analysis_status", sa.String(50), nullable=False), sa.Column("changed_article_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("impacted_rule_count", sa.Integer(), nullable=False, server_default="0"), sa.Column("changed_articles_json", sa.JSON()),
        sa.Column("impacted_rules_json", sa.JSON()), sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("analyzed_at", sa.DateTime(timezone=True)), sa.Column("idempotency_key", sa.String(64), nullable=False),
        sa.Column("error_code", sa.String(100)), sa.Column("sanitized_error", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("idempotency_key", name="uq_live_law_change_events_idempotency_key"))
    op.create_index("ix_live_law_change_events_law_msts", "live_law_change_events", ["law_id", "from_mst", "to_mst"])
    op.create_index("ix_live_law_change_events_analysis_status", "live_law_change_events", ["analysis_status"])
    op.create_table("live_law_change_event_audits", sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("event_id", sa.Integer(), sa.ForeignKey("live_law_change_events.id", ondelete="CASCADE"), nullable=False),
        sa.Column("action", sa.String(50), nullable=False), sa.Column("status", sa.String(50), nullable=False),
        sa.Column("sanitized_detail_json", sa.JSON()), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.create_index("ix_live_law_change_event_audits_event_created", "live_law_change_event_audits", ["event_id", "created_at"])
def downgrade():
    op.drop_table("live_law_change_event_audits")
    op.drop_table("live_law_change_events")
