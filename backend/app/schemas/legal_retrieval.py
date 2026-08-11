from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

SourceType = Literal["article", "attached_table"]


class LegalRetrievalRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    as_of: date
    top_k: int = Field(default=5, ge=1, le=50)
    source_types: list[SourceType] | None = None


class LegalRetrievalResult(BaseModel):
    source_type: SourceType
    law_identifier: str
    law_name: str
    source_identifier: str
    title: str
    text: str
    text_excerpt: str
    effective_date: date
    version_status: str
    mst: str | None = None
    provenance: dict[str, object] = Field(default_factory=dict)
    citation_id: str
    content_hash: str
    relevance_score: float


class LegalRetrievalResponse(BaseModel):
    query: str
    as_of: date
    top_k: int
    results: list[LegalRetrievalResult]
    retrieval_strategy: str = "deterministic_lexical_v1"
    vector_status: str = "not_configured"
