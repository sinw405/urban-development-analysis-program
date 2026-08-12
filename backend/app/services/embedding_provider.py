from __future__ import annotations
from collections import Counter
import hashlib
import math
from typing import Protocol, Sequence
import httpx
from app.services.legal_retrieval_service import normalize_search_text

class EmbeddingProvider(Protocol):
    provider_id: str
    model_id: str
    dimension: int
    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]: ...
    def embed_query(self, text: str) -> list[float]: ...

class EmbeddingProviderUnavailable(RuntimeError): pass

class UnavailableProductionEmbeddingProvider:
    provider_id = model_id = "unavailable"
    dimension = 0
    def embed_documents(self, texts): raise EmbeddingProviderUnavailable("Production embedding provider is not configured.")
    def embed_query(self, text): raise EmbeddingProviderUnavailable("Production embedding provider is not configured.")

class DeterministicTestEmbeddingProvider:
    """TEST_ONLY: explicit test injection only; never selected from settings."""
    provider_id = model_id = "deterministic-test-only-v1"
    def __init__(self, dimension: int = 64): self.dimension = dimension
    def _embed(self, text: str) -> list[float]:
        vector=[0.0]*self.dimension
        for token,count in Counter(normalize_search_text(text).split()).items():
            vector[int.from_bytes(hashlib.sha256(token.encode()).digest()[:4],"big")%self.dimension]+=float(count)
        norm=math.sqrt(sum(value*value for value in vector))
        return vector if norm == 0 else [value/norm for value in vector]
    def embed_documents(self,texts): return [self._embed(text) for text in texts]
    def embed_query(self,text): return self._embed(text)

class OpenAICompatibleEmbeddingProvider:
    provider_id = "openai-compatible"
    def __init__(self, *, base_url: str, api_key: str, model_id: str, dimension: int, timeout_seconds: float = 15.0):
        if not api_key or not model_id or dimension <= 0: raise EmbeddingProviderUnavailable("Embedding provider configuration is incomplete.")
        self.base_url,self._api_key,self.model_id=base_url.rstrip("/"),api_key,model_id
        self.dimension,self.timeout_seconds=dimension,timeout_seconds
    def embed_documents(self,texts):
        if not texts: return []
        try:
            response=httpx.post(f"{self.base_url}/embeddings",headers={"Authorization":f"Bearer {self._api_key}"},json={"model":self.model_id,"input":list(texts)},timeout=self.timeout_seconds)
            response.raise_for_status(); rows=sorted(response.json()["data"],key=lambda row:row["index"]); vectors=[row["embedding"] for row in rows]
            if len(vectors)!=len(texts) or any(len(vector)!=self.dimension for vector in vectors): raise EmbeddingProviderUnavailable("Embedding provider returned an unexpected vector shape.")
            return vectors
        except (httpx.HTTPError,KeyError,TypeError,ValueError) as exc: raise EmbeddingProviderUnavailable("Embedding provider request failed.") from exc
    def embed_query(self,text): return self.embed_documents([text])[0]

def production_embedding_provider(settings):
    if not settings.embedding_configured: return None
    return OpenAICompatibleEmbeddingProvider(base_url=settings.embedding_base_url,api_key=settings.embedding_api_key,model_id=settings.embedding_model,dimension=settings.embedding_dimension,timeout_seconds=settings.embedding_timeout_seconds)
