from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.legal_retrieval import LegalRetrievalResult, SourceType


class LegalAnswerRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=500)
    as_of: date
    retrieval_mode: Literal['lexical', 'vector', 'hybrid'] = 'lexical'
    top_k: int = Field(default=5, ge=1, le=20)
    source_types: list[SourceType] | None = None


class GroundedClaim(BaseModel):
    text: str = Field(..., min_length=1)
    citation_ids: list[str] = Field(..., min_length=1)


class GenerationDraft(BaseModel):
    status: Literal['grounded', 'insufficient_evidence', 'conflicting_evidence']
    claims: list[GroundedClaim] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class LegalCitation(BaseModel):
    citation_id: str
    law_identifier: str
    law_name: str
    source_type: SourceType
    source_identifier: str
    title: str
    effective_date: date
    mst: str | None = None
    provenance: dict[str, object] = Field(default_factory=dict)
    excerpt: str
    content_hash: str


class LegalAnswerResponse(BaseModel):
    status: Literal['grounded', 'grounded_with_conflicts', 'insufficient_evidence', 'generation_unavailable', 'validation_failed']
    answer: str | None = None
    claims: list[GroundedClaim] = Field(default_factory=list)
    citations: list[LegalCitation] = Field(default_factory=list)
    evidence: list[LegalRetrievalResult] = Field(default_factory=list)
    as_of: date
    retrieval_mode: str
    retrieval_status: str
    generation_status: str
    provider_status: str
    retrieval_fallback_used: bool = False
    disclaimer: str
    warnings: list[str] = Field(default_factory=list)
