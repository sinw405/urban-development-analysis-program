"""add phase44 scheduler registry and run history
Revision ID: 0010_phase44_scheduler
Revises: 0009_phase43_live_events
"""
from alembic import op
import sqlalchemy as sa
revision = "0010_phase44_scheduler"
down_revision = "0009_phase43_live_events"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("law_update_registry",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("law_identifier", sa.String(100), nullable=False, unique=True),
        sa.Column("law_name", sa.String(255), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_checked_at", sa.DateTime(timezone=True)),
        sa.Column("last_success_at", sa.DateTime(timezone=True)),
        sa.Column("last_detected_mst", sa.String(100)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.create_table("law_update_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("trigger_type", sa.String(20), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("target_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("success_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("no_change_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("change_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_event_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duration_ms", sa.Integer()), sa.Column("sanitized_error", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.create_table("law_update_run_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("run_id", sa.Integer(), sa.ForeignKey("law_update_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("registry_id", sa.Integer(), sa.ForeignKey("law_update_registry.id", ondelete="SET NULL")),
        sa.Column("law_identifier", sa.String(100), nullable=False), sa.Column("law_name", sa.String(255), nullable=False),
        sa.Column("status", sa.String(30), nullable=False), sa.Column("from_mst", sa.String(100)), sa.Column("to_mst", sa.String(100)),
        sa.Column("version_changed", sa.Boolean()), sa.Column("content_changed", sa.Boolean()),
        sa.Column("event_id", sa.Integer(), sa.ForeignKey("live_law_change_events.id", ondelete="SET NULL")),
        sa.Column("event_created", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False), sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("duration_ms", sa.Integer()), sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_code", sa.String(100)), sa.Column("sanitized_error", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.create_index("ix_law_update_run_items_run_law", "law_update_run_items", ["run_id", "law_identifier"])

def downgrade():
    op.drop_table("law_update_run_items")
    op.drop_table("law_update_runs")
    op.drop_table("law_update_registry")