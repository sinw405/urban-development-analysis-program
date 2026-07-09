from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select

from app.core.database import SessionLocal
from app.main import app
from app.models import (
    OfficialLawArticleRecord,
    OfficialLawDocument,
    OfficialLawIngestRun,
    OfficialLawSourceEvidence,
    ProcedureOfficialArticleCandidate,
)

client = TestClient(app)
ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
JSON_MANIFEST = FIXTURES / "moleg_seed_manifest.json"
MANUAL_JSON = FIXTURES / "moleg_manual_import_sample.json"
LAW_NAME = "TEST_PHASE27_MANUAL_LAW_DO_NOT_USE"
MST_JSON = "PHASE27_MANUAL_MST_JSON"
ARTICLE_TITLE = "TEST_PHASE27_ARTICLE_TITLE_JSON"
SECRET_LIKE = "TEST_PHASE29_SECRET_SHOULD_NOT_APPEAR"


def _cleanup() -> None:
    db = SessionLocal()
    try:
        db.execute(delete(ProcedureOfficialArticleCandidate).where(ProcedureOfficialArticleCandidate.mst == MST_JSON))
        run_ids = list(
            db.scalars(
                select(OfficialLawIngestRun.id).where(
                    OfficialLawIngestRun.source_mode.in_(["official_seed", "official_manual"]),
                    OfficialLawIngestRun.query.in_([LAW_NAME, MANUAL_JSON.name]),
                )
            ).all()
        )
        if run_ids:
            db.execute(delete(OfficialLawSourceEvidence).where(OfficialLawSourceEvidence.ingest_run_id.in_(run_ids)))
            db.execute(delete(OfficialLawIngestRun).where(OfficialLawIngestRun.id.in_(run_ids)))
        document_ids = list(db.scalars(select(OfficialLawDocument.id).where(OfficialLawDocument.mst == MST_JSON)).all())
        if document_ids:
            db.execute(delete(ProcedureOfficialArticleCandidate).where(ProcedureOfficialArticleCandidate.document_id.in_(document_ids)))
            db.execute(delete(OfficialLawArticleRecord).where(OfficialLawArticleRecord.document_id.in_(document_ids)))
            db.execute(delete(OfficialLawDocument).where(OfficialLawDocument.id.in_(document_ids)))
        db.commit()
    finally:
        db.close()


def _import_seed() -> dict:
    response = client.post("/api/legal-references/official-law-seed-import", json={"manifest_path": str(JSON_MANIFEST)})
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    return data


def _import_manual() -> dict:
    response = client.post(
        "/api/legal-references/official-law-manual-import",
        json={"file_path": str(MANUAL_JSON), "query": LAW_NAME},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    return data


def test_procedure_candidate_endpoint_returns_200_without_official_articles():
    _cleanup()
    try:
        response = client.get("/api/legal-references/procedure-article-candidates", params={"include_unmatched": "true"})
        data = response.json()
        assert response.status_code == 200
        assert data["items"]
        assert data["unmatched_steps"]
        assert data["warnings"]
    finally:
        _cleanup()


def test_seed_fixture_generates_unconfirmed_official_seed_db_candidate():
    _cleanup()
    try:
        _import_seed()
        response = client.get(
            "/api/legal-references/procedure-article-candidates",
            params={"procedure_code": "PROJECT_BASIC_REVIEW", "law_title": LAW_NAME},
        )
        data = response.json()
        assert response.status_code == 200
        candidate = data["items"][0]["candidates"][0]
        assert candidate["source_mode"] == "official_db"
        assert candidate["source_mode_detail"] == "official_seed_db"
        assert candidate["match_method"] == "title_keyword"
        assert candidate["match_status"] == "candidate"
        assert candidate["confidence_level"] == "high"
        assert candidate["is_confirmed"] is False
        assert candidate["article_title"] == ARTICLE_TITLE
        assert candidate["article_no"] is not None

        db = SessionLocal()
        try:
            stored = db.scalar(select(ProcedureOfficialArticleCandidate).where(ProcedureOfficialArticleCandidate.id == candidate["id"]))
            assert stored is not None
            assert stored.is_confirmed is False
            assert stored.source_mode_detail == "official_seed_db"
            assert stored.article_no == candidate["article_no"]
        finally:
            db.close()
    finally:
        _cleanup()


def test_manual_fixture_generates_manual_db_candidate_and_preserves_distinction():
    _cleanup()
    try:
        _import_manual()
        response = client.get(
            "/api/legal-references/procedure-article-candidates",
            params={"procedure_code": "PROJECT_BASIC_REVIEW", "source_mode_detail": "official_manual_db"},
        )
        data = response.json()
        assert response.status_code == 200
        candidate = data["items"][0]["candidates"][0]
        assert candidate["source_mode"] == "official_db"
        assert candidate["source_mode_detail"] == "official_manual_db"
        assert candidate["is_confirmed"] is False
    finally:
        _cleanup()


def test_duplicate_candidate_generation_reuses_candidate_row():
    _cleanup()
    try:
        _import_seed()
        params = {"procedure_code": "PROJECT_BASIC_REVIEW", "law_title": LAW_NAME}
        first = client.get("/api/legal-references/procedure-article-candidates", params=params).json()
        second = client.get("/api/legal-references/procedure-article-candidates", params=params).json()
        first_ids = [candidate["id"] for candidate in first["items"][0]["candidates"]]
        second_ids = [candidate["id"] for candidate in second["items"][0]["candidates"]]
        assert first_ids == second_ids
        db = SessionLocal()
        try:
            count = db.scalar(select(func.count()).select_from(ProcedureOfficialArticleCandidate).where(ProcedureOfficialArticleCandidate.mst == MST_JSON))
            assert count == len(first_ids)
        finally:
            db.close()
    finally:
        _cleanup()


def test_analyze_includes_optional_candidate_fields_and_preserves_13_procedures():
    _cleanup()
    try:
        _import_seed()
        response = client.post(
            "/api/analyze",
            json={
                "project_name": "Phase29 Candidate Project",
                "location": "Seongnam-si, Gyeonggi-do",
                "area_square_meters": 100000,
                "implementation_method": "expropriation_or_use",
                "implementer_type": "public",
                "local_government": "Seongnam-si",
            },
        )
        data = response.json()
        assert response.status_code == 200
        assert len(data["procedures"]) == 13
        by_code = {step["step_code"]: step for step in data["procedures"]}
        step = by_code["PROJECT_BASIC_REVIEW"]
        assert step["reference_candidate_count"] >= 1
        assert step["reference_status"] == "official_candidate_available"
        assert step["official_article_candidates"][0]["source_mode_detail"] == "official_seed_db"
        assert step["official_article_candidates"][0]["is_confirmed"] is False
    finally:
        _cleanup()


def test_snapshot_diagnostic_includes_candidate_counts_and_no_secret_like_values():
    _cleanup()
    try:
        _import_seed()
        client.get("/api/legal-references/procedure-article-candidates", params={"procedure_code": "PROJECT_BASIC_REVIEW", "law_title": LAW_NAME})
        response = client.get("/api/legal-references/official-law-snapshot")
        data = response.json()
        assert response.status_code == 200
        assert data["procedure_candidate_count"] >= 1
        assert data["confirmed_reference_count"] == 0
        assert data["unconfirmed_candidate_count"] >= 1
        assert "official_seed_db" in data["candidate_source_modes"]
        assert data["latest_candidate_generated_at"] is not None
        assert SECRET_LIKE not in str(data)
    finally:
        _cleanup()


def test_candidate_evidence_keeps_raw_payload_out_of_sanitized_summary():
    _cleanup()
    try:
        _import_seed()
        db = SessionLocal()
        try:
            evidence = db.scalar(select(OfficialLawSourceEvidence).join(OfficialLawIngestRun).where(OfficialLawIngestRun.source_mode == "official_seed", OfficialLawIngestRun.query == LAW_NAME))
            assert evidence is not None
            dumped = str(evidence.sanitized_summary_json)
            assert evidence.redaction_applied is True
            assert "TEST_PHASE27_ARTICLE_TEXT_JSON" not in dumped
            assert "MOLEG_API_KEY" not in dumped
            assert "MOLEG_OC" not in dumped
        finally:
            db.close()
    finally:
        _cleanup()

