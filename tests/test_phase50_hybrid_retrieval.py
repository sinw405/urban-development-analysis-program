from datetime import date
from fastapi.testclient import TestClient
from app.core.database import SessionLocal
from app.main import app
from app.services.embedding_provider import DeterministicTestEmbeddingProvider, UnavailableProductionEmbeddingProvider
from app.services.hybrid_legal_retrieval_service import retrieve_vector_evidence, retrieve_with_mode
from app.services.legal_retrieval_service import build_legal_corpus, retrieve_legal_evidence
from app.services.legal_vector_index_service import InMemoryLegalVectorIndex
from tests.test_phase49_legal_retrieval import KEY, _cleanup, _seed

client=TestClient(app)


def test_deterministic_provider_and_incremental_content_hash_index():
    _cleanup(); _seed()
    try:
        provider=DeterministicTestEmbeddingProvider(); index=InMemoryLegalVectorIndex()
        with SessionLocal() as db: corpus=build_legal_corpus(db,date(2026,1,1))
        first=index.index_changed_sources(corpus,provider); second=index.index_changed_sources(corpus,provider)
        assert first["indexed"] == len(corpus) and second["indexed"] == 0
        assert second["unchanged"] == len(corpus)
    finally: _cleanup()


def test_vector_and_hybrid_preserve_citations_and_as_of():
    _cleanup(); _seed()
    try:
        provider=DeterministicTestEmbeddingProvider(); index=InMemoryLegalVectorIndex()
        with SessionLocal() as db:
            vector=retrieve_vector_evidence(db,"도시개발구역 지정",date(2026,1,1),50,None,provider,index)
            hybrid,status,fallback=retrieve_with_mode(db,"도시개발구역 지정",date(2026,1,1),10,None,"hybrid",provider,index)
        fixture=next(item for item in vector if item.law_identifier==KEY)
        assert fixture.mst == "200" and fixture.citation_id and fixture.content_hash
        assert all("미래 예정" not in item.text for item in vector)
        assert status == "available" and fallback is False
        assert all(item.citation_id for item in hybrid)
        assert len({item.citation_id for item in hybrid}) == len(hybrid)
    finally: _cleanup()


def test_attached_table_vector_retrieval():
    _cleanup(); _seed()
    try:
        with SessionLocal() as db:
            results=retrieve_vector_evidence(db,"환경영향평가 대상",date(2026,1,1),50,["attached_table"],DeterministicTestEmbeddingProvider(),InMemoryLegalVectorIndex())
        assert any(item.law_identifier==KEY and item.source_type=="attached_table" for item in results)
    finally: _cleanup()


def test_vector_unavailable_falls_back_to_lexical_without_500():
    response=client.post('/api/rag/retrieve',json={"query":"개발계획","as_of":"2026-01-01","top_k":5,"retrieval_mode":"hybrid"})
    assert response.status_code==200
    data=response.json(); assert data["fallback_used"] is True
    assert data["vector_status"] == "unavailable"
    assert data["retrieval_strategy"] == "deterministic_lexical_v1"


def test_hybrid_does_not_drop_lexical_baseline_fixture():
    _cleanup(); _seed()
    try:
        with SessionLocal() as db:
            lexical=retrieve_legal_evidence(db,"도시개발구역 지정",date(2026,1,1),50)
            hybrid,_,_=retrieve_with_mode(db,"도시개발구역 지정",date(2026,1,1),50,None,"hybrid",DeterministicTestEmbeddingProvider(),InMemoryLegalVectorIndex())
        lexical_fixture={x.citation_id for x in lexical if x.law_identifier==KEY}
        hybrid_ids={x.citation_id for x in hybrid}
        assert lexical_fixture and lexical_fixture <= hybrid_ids
    finally: _cleanup()
