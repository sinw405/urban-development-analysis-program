from datetime import date, datetime
from typing import Any
from pgvector.sqlalchemy import Vector
from sqlalchemy import Date, DateTime, Index, Integer, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base

class LegalSourceEmbedding(Base):
    __tablename__="legal_source_embeddings"
    __table_args__=(UniqueConstraint("provider_id","model_id","source_identifier",name="uq_legal_embedding_provider_source"),Index("ix_legal_embedding_lookup","provider_id","model_id","source_type","effective_date"))
    id: Mapped[int]=mapped_column(primary_key=True)
    provider_id: Mapped[str]=mapped_column(String(100),nullable=False)
    model_id: Mapped[str]=mapped_column(String(200),nullable=False)
    embedding_dimension: Mapped[int]=mapped_column(Integer,nullable=False)
    source_type: Mapped[str]=mapped_column(String(30),nullable=False)
    source_identifier: Mapped[str]=mapped_column(String(300),nullable=False)
    law_identifier: Mapped[str]=mapped_column(String(200),nullable=False)
    law_name: Mapped[str]=mapped_column(String(500),nullable=False)
    title: Mapped[str]=mapped_column(String(500),nullable=False)
    source_text: Mapped[str]=mapped_column(Text,nullable=False)
    text_excerpt: Mapped[str]=mapped_column(Text,nullable=False)
    effective_date: Mapped[date]=mapped_column(Date,nullable=False)
    version_status: Mapped[str]=mapped_column(String(100),nullable=False)
    mst: Mapped[str|None]=mapped_column(String(100))
    provenance_json: Mapped[dict[str,Any]]=mapped_column(JSON,nullable=False)
    citation_id: Mapped[str]=mapped_column(String(500),nullable=False)
    content_hash: Mapped[str]=mapped_column(String(64),nullable=False)
    embedding: Mapped[list[float]]=mapped_column(Vector(),nullable=False)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now(),nullable=False)
    updated_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now(),onupdate=func.now(),nullable=False)
