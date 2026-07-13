"""cascade fixture candidate cleanup for phase 40 event tables

Revision ID: 0008_phase40_event_fk_cascade
Revises: 0007_law_change_impact
Create Date: 2026-07-14 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0008_phase40_event_fk_cascade"
down_revision: Union[str, Sequence[str], None] = "0007_law_change_impact"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _fk_names(table_name: str, referred_table: str) -> list[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return [fk["name"] for fk in inspector.get_foreign_keys(table_name) if fk.get("referred_table") == referred_table and fk.get("name")]


def upgrade() -> None:
    for table_name in ["procedure_article_review_events", "law_change_impact_events"]:
        for fk_name in _fk_names(table_name, "procedure_official_article_candidates"):
            op.drop_constraint(fk_name, table_name, type_="foreignkey")
        op.create_foreign_key(
            f"{table_name}_candidate_id_fkey",
            table_name,
            "procedure_official_article_candidates",
            ["candidate_id"],
            ["id"],
            ondelete="CASCADE",
        )


def downgrade() -> None:
    for table_name in ["procedure_article_review_events", "law_change_impact_events"]:
        for fk_name in _fk_names(table_name, "procedure_official_article_candidates"):
            op.drop_constraint(fk_name, table_name, type_="foreignkey")
        op.create_foreign_key(
            f"{table_name}_candidate_id_fkey",
            table_name,
            "procedure_official_article_candidates",
            ["candidate_id"],
            ["id"],
        )
