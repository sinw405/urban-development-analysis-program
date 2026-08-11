from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.core.database import SessionLocal
from app.main import app
from app.models import Law, LawArticle, LawArticleVersion, LawAttachedTableEvidence
from app.services.legal_retrieval_service import normalize_search_text, retrieve_legal_evidence

client = TestClient(app)
KEY = "PHASE49_TEST_LAW_DO_NOT_USE"


def _cleanup():
    with SessionLocal() as db:
        laws = list(db.scalars(select(Law).where(Law.law_key == KEY)).all())
        for law in laws:
            db.execute(delete(LawAttachedTableEvidence).where(LawAttachedTableEvidence.law_id == law.id))
            article_ids = list(db.scalars(select(LawArticle.id).where(LawArticle.law_id == law.id)))
            if article_ids:
                db.execute(delete(LawArticleVersion).where(LawArticleVersion.law_article_id.in_(article_ids)))
                db.execute(delete(LawArticle).where(LawArticle.id.in_(article_ids)))
            db.delete(law)
        db.commit()


def _seed():
    with SessionLocal() as db:
        law = Law(law_name="도시개발 검색검증법", law_key=KEY, source="TEST", mapping_status="verified")
        db.add(law); db.flush()
        article = LawArticle(law_id=law.id, article_key="TEST_ARTICLE", article_number_text="1", article_title="도시개발구역 지정", mapping_status="verified")
        db.add(article); db.flush()
        for effective, text, source, status in [
            (date(2024,1,1), "과거 도시개발구역 지정 절차", "MOLEG_LIVE:100", "historical"),
            (date(2025,1,1), "현재 도시개발구역 지정 및 개발계획", "MOLEG_LIVE:200", "current"),
            (date(2027,1,1), "미래 예정 실시계획 인가", "MOLEG_LIVE:300", "scheduled"),
        ]:
            db.add(LawArticleVersion(law_article_id=article.id, effective_date=effective, article_text=text, source=source, version_status=status))
        db.add(LawAttachedTableEvidence(
            law_id=law.id, table_key="table:1", table_number="0001", table_title="환경영향평가 대상사업",
            mst="200", effective_date=date(2025,1,1), normalized_text="도시개발사업 환경영향평가 대상 범위",
            source="TEST", provenance_json={"source":"TEST", "secret_exposed":False},
        ))
        db.commit()


def test_text_normalization_is_minimal_and_deterministic():
    assert normalize_search_text("  도시개발구역\n지정! ") == "도시개발구역 지정"


def test_article_retrieval_is_as_of_aware_and_citation_ready():
    _cleanup(); _seed()
    try:
        with SessionLocal() as db:
            old = retrieve_legal_evidence(db, "도시개발구역 지정", date(2024,6,1), 50, ["article"])
            current = retrieve_legal_evidence(db, "도시개발구역 지정", date(2026,6,1), 50, ["article"])
        old_fixture = next(item for item in old if item.law_identifier == KEY)
        current_fixture = next(item for item in current if item.law_identifier == KEY)
        assert old_fixture.mst == "100" and "\uacfc\uac70" in old_fixture.text
        assert current_fixture.mst == "200" and "\ud604\uc7ac" in current_fixture.text
        assert all("\ubbf8\ub798 \uc608\uc815" not in item.text for item in current)
        assert current_fixture.citation_id and len(current_fixture.content_hash) == 64
    finally: _cleanup()


def test_attached_table_is_retrievable_in_top_k():
    _cleanup(); _seed()
    try:
        with SessionLocal() as db:
            results = retrieve_legal_evidence(db, "환경영향평가 대상", date(2026,1,1), 50, ["attached_table"])
        fixture = next(item for item in results if item.law_identifier == KEY)
        assert fixture.source_type == "attached_table"
        assert fixture.title == "\ud658\uacbd\uc601\ud5a5\ud3c9\uac00 \ub300\uc0c1\uc0ac\uc5c5"
        assert fixture.provenance["secret_exposed"] is False
    finally: _cleanup()


def test_empty_result_and_source_filter_are_safe():
    with SessionLocal() as db:
        assert retrieve_legal_evidence(db, "절대존재하지않는검색어", date(2026,1,1), 5) == []


def test_api_is_additive_and_returns_typed_metadata():
    _cleanup(); _seed()
    try:
        response = client.post("/api/rag/retrieve", json={"query":"환경영향평가 대상", "as_of":"2026-01-01", "top_k":5, "source_types":["attached_table"]})
        assert response.status_code == 200
        data=response.json(); assert data["retrieval_strategy"] == "deterministic_lexical_v1"
        assert data["vector_status"] == "not_configured"
        assert data["results"][0]["source_type"] == "attached_table"
    finally: _cleanup()
