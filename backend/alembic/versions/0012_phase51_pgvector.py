"""phase 51 pgvector persistence
Revision ID: 0012_phase51_pgvector
Revises: 0011_phase48_attached_tables
"""
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
revision="0012_phase51_pgvector"
down_revision="0011_phase48_attached_tables"
branch_labels=depends_on=None

def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table("legal_source_embeddings",
        sa.Column("id",sa.Integer(),primary_key=True),sa.Column("provider_id",sa.String(100),nullable=False),sa.Column("model_id",sa.String(200),nullable=False),sa.Column("embedding_dimension",sa.Integer(),nullable=False),
        sa.Column("source_type",sa.String(30),nullable=False),sa.Column("source_identifier",sa.String(300),nullable=False),sa.Column("law_identifier",sa.String(200),nullable=False),sa.Column("law_name",sa.String(500),nullable=False),sa.Column("title",sa.String(500),nullable=False),
        sa.Column("source_text",sa.Text(),nullable=False),sa.Column("text_excerpt",sa.Text(),nullable=False),sa.Column("effective_date",sa.Date(),nullable=False),sa.Column("version_status",sa.String(100),nullable=False),sa.Column("mst",sa.String(100)),
        sa.Column("provenance_json",sa.JSON(),nullable=False),sa.Column("citation_id",sa.String(500),nullable=False),sa.Column("content_hash",sa.String(64),nullable=False),sa.Column("embedding",Vector(),nullable=False),
        sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),sa.Column("updated_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),
        sa.UniqueConstraint("provider_id","model_id","source_identifier",name="uq_legal_embedding_provider_source"))
    op.create_index("ix_legal_embedding_lookup","legal_source_embeddings",["provider_id","model_id","source_type","effective_date"])

def downgrade():
    op.drop_index("ix_legal_embedding_lookup",table_name="legal_source_embeddings")
    op.drop_table("legal_source_embeddings")
    op.execute("DROP EXTENSION IF EXISTS vector")
