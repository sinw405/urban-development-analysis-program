from __future__ import annotations
from collections import Counter
import hashlib
import math
from typing import Protocol, Sequence

from app.services.legal_retrieval_service import normalize_search_text


class EmbeddingProvider(Protocol):
    provider_id: str
    dimension: int
    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]: ...
    def embed_query(self, text: str) -> list[float]: ...


class EmbeddingProviderUnavailable(RuntimeError):
    pass


class UnavailableProductionEmbeddingProvider:
    provider_id = "unavailable"
    dimension = 0
    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        raise EmbeddingProviderUnavailable("Production embedding provider is not configured.")
    def embed_query(self, text: str) -> list[float]:
        raise EmbeddingProviderUnavailable("Production embedding provider is not configured.")


class DeterministicTestEmbeddingProvider:
    """TEST_ONLY provider. It must be injected explicitly and is never selected from settings."""
    provider_id = "deterministic-test-only-v1"
    def __init__(self, dimension: int = 64): self.dimension = dimension
    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimension
        tokens = normalize_search_text(text).split()
        for token, count in Counter(tokens).items():
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimension
            vector[index] += float(count)
        norm = math.sqrt(sum(value * value for value in vector))
        return vector if norm == 0 else [value / norm for value in vector]
    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]: return [self._embed(text) for text in texts]
    def embed_query(self, text: str) -> list[float]: return self._embed(text)
