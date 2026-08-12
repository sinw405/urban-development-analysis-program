from __future__ import annotations
from dataclasses import dataclass
import math
from typing import Iterable

from app.schemas.legal_retrieval import LegalRetrievalResult
from app.services.embedding_provider import EmbeddingProvider


@dataclass
class VectorIndexEntry:
    content_hash: str
    source_identifier: str
    provider_id: str
    embedding: list[float]
    document: LegalRetrievalResult


class InMemoryLegalVectorIndex:
    """Vector-ready fallback index; production persistence requires pgvector support."""
    def __init__(self): self._entries: dict[tuple[str, str], VectorIndexEntry] = {}
    def index_changed_sources(self, documents: list[LegalRetrievalResult], provider: EmbeddingProvider) -> dict[str, int]:
        wanted = {(provider.provider_id, item.source_identifier): item for item in documents}
        stale = [key for key in self._entries if key[0] == provider.provider_id and key not in wanted]
        for key in stale: del self._entries[key]
        changed = [item for key, item in wanted.items() if key not in self._entries or self._entries[key].content_hash != item.content_hash]
        vectors = provider.embed_documents([item.text for item in changed])
        for item, vector in zip(changed, vectors):
            self._entries[(provider.provider_id, item.source_identifier)] = VectorIndexEntry(item.content_hash, item.source_identifier, provider.provider_id, vector, item.model_copy(deep=True))
        return {"indexed": len(changed), "unchanged": len(documents) - len(changed), "removed": len(stale)}
    def search(self, query_vector: list[float], provider_id: str, top_k: int) -> list[tuple[LegalRetrievalResult, float]]:
        scored=[]
        for (entry_provider, _), entry in self._entries.items():
            if entry_provider != provider_id: continue
            score=sum(a*b for a,b in zip(query_vector,entry.embedding))
            if score > 0: scored.append((entry.document.model_copy(deep=True), round(score,6)))
        scored.sort(key=lambda pair:(-pair[1],pair[0].citation_id))
        return scored[:top_k]
