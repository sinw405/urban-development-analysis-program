from pathlib import Path
from unittest.mock import patch
import httpx
import pytest
from app.core.config import Settings
from app.schemas.legal_retrieval import LegalRetrievalResponse
from app.services.embedding_provider import DeterministicTestEmbeddingProvider, EmbeddingProviderUnavailable, OpenAICompatibleEmbeddingProvider, production_embedding_provider
from app.services.hybrid_legal_retrieval_service import retrieve_with_mode
from app.services.postgres_legal_vector_repository import VectorBackendUnavailable


def test_pgvector_configuration_and_migration_chain():
    compose=Path("docker-compose.yml").read_text(encoding="utf-8-sig")
    migration=Path("backend/alembic/versions/0012_phase51_pgvector.py").read_text(encoding="utf-8-sig")
    assert "pgvector/pgvector:pg16" in compose
    assert 'down_revision="0011_phase48_attached_tables"' in migration
    assert "CREATE EXTENSION IF NOT EXISTS vector" in migration and "Vector()" in migration


def test_production_configuration_never_selects_test_provider(monkeypatch):
    for name in ("EMBEDDING_PROVIDER","EMBEDDING_API_KEY","EMBEDDING_MODEL","EMBEDDING_DIMENSION"): monkeypatch.delenv(name,raising=False)
    assert production_embedding_provider(Settings()) is None
    monkeypatch.setenv("EMBEDDING_PROVIDER","deterministic-test-only-v1")
    monkeypatch.setenv("EMBEDDING_API_KEY","secret")
    monkeypatch.setenv("EMBEDDING_MODEL","model")
    monkeypatch.setenv("EMBEDDING_DIMENSION","3")
    assert production_embedding_provider(Settings()) is None
    assert DeterministicTestEmbeddingProvider().provider_id.startswith("deterministic-test-only")


def test_production_provider_batches_and_hides_secret():
    provider=OpenAICompatibleEmbeddingProvider(base_url="https://example.invalid/v1",api_key="top-secret",model_id="model",dimension=3)
    response=type("Response",(),{"raise_for_status":lambda self:None,"json":lambda self:{"data":[{"index":1,"embedding":[0,1,0]},{"index":0,"embedding":[1,0,0]}]}})()
    with patch("app.services.embedding_provider.httpx.post",return_value=response): assert provider.embed_documents(["a","b"])==[[1,0,0],[0,1,0]]
    with patch("app.services.embedding_provider.httpx.post",side_effect=httpx.TimeoutException("top-secret")):
        with pytest.raises(EmbeddingProviderUnavailable) as exc: provider.embed_query("q")
    assert "top-secret" not in str(exc.value)


def test_api_response_contract_is_additive():
    data=LegalRetrievalResponse(query="q",as_of="2026-01-01",top_k=5,results=[]).model_dump()
    assert data["vector_status"]=="not_configured" and data["provider_status"]=="not_configured" and data["backend_status"]=="not_checked"


def test_backend_failure_uses_lexical_fallback(monkeypatch):
    lexical=[]
    monkeypatch.setattr("app.services.hybrid_legal_retrieval_service.retrieve_legal_evidence",lambda *a,**k:lexical)
    monkeypatch.setattr("app.services.hybrid_legal_retrieval_service.retrieve_vector_evidence",lambda *a,**k:(_ for _ in ()).throw(VectorBackendUnavailable()))
    results,status,fallback=retrieve_with_mode(object(),"q",__import__("datetime").date(2026,1,1),5,mode="hybrid",provider=object(),index=object())
    assert results==[] and status=="backend_unavailable" and fallback is True
