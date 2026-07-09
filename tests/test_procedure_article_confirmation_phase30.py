import json
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
from scripts.validate_procedure_article_seeds import main as validate_seed_main, validate_seed_file

client = TestClient(app)
ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
JSON_MANIFEST = FIXTURES / "moleg_seed_manifest.json"
LAW_NAME = "TEST_PHASE27_MANUAL_LAW_DO_NOT_USE"
MST_JSON = "PHASE27_MANUAL_MST_JSON"
SECRET_LIKE = "TEST_PHASE30_SECRET_SHOULD_NOT_APPEAR"


def _cleanup() -> None:
    db = SessionLocal()
    try:
        document_ids = list(db.scalars(select(OfficialLawDocument.id).where(OfficialLawDocument.mst == MST_JSON)).all())
        if document_ids:
            db.execute(delete(ProcedureOfficialArticleCandidate).where(ProcedureOfficialArticleCandidate.document_id.in_(document_ids)))
            db.execute(delete(OfficialLawArticleRecord).where(OfficialLawArticleRecord.document_id.in_(document_ids)))
            db.execute(delete(OfficialLawDocument).where(OfficialLawDocument.id.in_(document_ids)))
        run_ids = list(db.scalars(select(OfficialLawIngestRun.id).where(OfficialLawIngestRun.source_mode == "official_seed", OfficialLawIngestRun.query == LAW_NAME)).all())
        if run_ids:
            db.execute(delete(OfficialLawSourceEvidence).where(OfficialLawSourceEvidence.ingest_run_id.in_(run_ids)))
            db.execute(delete(OfficialLawIngestRun).where(OfficialLawIngestRun.id.in_(run_ids)))
        db.commit()
    finally:
        db.close()


def _import_seed_and_generate_candidates() -> list[dict]:
    seed = client.post("/api/legal-references/official-law-seed-import", json={"manifest_path": str(JSON_MANIFEST)})
    assert seed.status_code == 200
    assert seed.json()["success"] is True
    response = client.get(
        "/api/legal-references/procedure-article-candidates",
        params={"procedure_code": "PROJECT_BASIC_REVIEW", "law_title": LAW_NAME},
    )
    assert response.status_code == 200
    candidates = response.json()["items"][0]["candidates"]
    assert candidates
    return candidates


def test_candidate_list_supports_confirmed_filter_and_metadata_fields():
    _cleanup()
    try:
        candidates = _import_seed_and_generate_candidates()
        candidate = candidates[0]
        assert candidate["is_confirmed"] is False
        assert "generated_at" in candidate
        assert "confirmed_at" in candidate
        confirmed_empty = client.get(
            "/api/legal-references/procedure-article-candidates",
            params={"procedure_code": "PROJECT_BASIC_REVIEW", "law_title": LAW_NAME, "is_confirmed": "true"},
        )
        assert confirmed_empty.status_code == 200
        assert confirmed_empty.json()["unmatched_steps"]
    finally:
        _cleanup()


def test_confirm_api_is_idempotent_and_unconfirm_resets_candidate():
    _cleanup()
    try:
        candidate_id = _import_seed_and_generate_candidates()[0]["id"]
        body = {"confirmed_by": "manual_admin", "confirmation_note": "TEST review note"}
        first = client.patch(f"/api/legal-references/procedure-article-candidates/{candidate_id}/confirm", json=body)
        second = client.post(f"/api/legal-references/procedure-article-candidates/{candidate_id}/confirm", json=body)
        assert first.status_code == 200
        assert second.status_code == 200
        assert first.json()["is_confirmed"] is True
        assert second.json()["is_confirmed"] is True
        assert second.json()["confirmed_by"] == "manual_admin"
        assert second.json()["confirmation_note"] == "TEST review note"
        assert second.json()["secret_exposed"] is False

        confirmed = client.get(
            "/api/legal-references/procedure-article-candidates",
            params={"procedure_code": "PROJECT_BASIC_REVIEW", "law_title": LAW_NAME, "is_confirmed": "true"},
        ).json()["items"][0]["candidates"]
        assert confirmed[0]["id"] == candidate_id
        assert confirmed[0]["is_confirmed"] is True

        unconfirmed = client.patch(
            f"/api/legal-references/procedure-article-candidates/{candidate_id}/unconfirm",
            json={"confirmation_note": "TEST needs review"},
        )
        assert unconfirmed.status_code == 200
        assert unconfirmed.json()["is_confirmed"] is False
        assert unconfirmed.json()["confirmed_at"] is None
        assert unconfirmed.json()["confirmation_note"] == "TEST needs review"
    finally:
        _cleanup()


def test_missing_candidate_id_returns_404():
    response = client.patch(
        "/api/legal-references/procedure-article-candidates/999999999/confirm",
        json={"confirmed_by": "manual_admin"},
    )
    assert response.status_code == 404


def test_analyze_prioritizes_confirmed_candidate_and_keeps_13_procedures():
    _cleanup()
    try:
        candidates = _import_seed_and_generate_candidates()
        second_id = candidates[1]["id"] if len(candidates) > 1 else candidates[0]["id"]
        confirm = client.patch(
            f"/api/legal-references/procedure-article-candidates/{second_id}/confirm",
            json={"confirmed_by": "manual_admin", "confirmation_note": "TEST confirmed candidate"},
        )
        assert confirm.status_code == 200
        response = client.post(
            "/api/analyze",
            json={
                "project_name": "Phase30 Confirmed Candidate Project",
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
        step = next(item for item in data["procedures"] if item["step_code"] == "PROJECT_BASIC_REVIEW")
        assert step["reference_status"] == "confirmed_reference_available"
        assert step["official_article_candidates"][0]["id"] == second_id
        assert step["official_article_candidates"][0]["is_confirmed"] is True
        assert step["official_article_candidates"][0]["confirmation_note"] == "TEST confirmed candidate"
    finally:
        _cleanup()


def test_snapshot_diagnostic_counts_confirmation_and_raw_payload_policy():
    _cleanup()
    try:
        candidate_id = _import_seed_and_generate_candidates()[0]["id"]
        client.patch(
            f"/api/legal-references/procedure-article-candidates/{candidate_id}/confirm",
            json={"confirmed_by": "manual_admin", "confirmation_note": "TEST confirmed"},
        )
        response = client.get("/api/legal-references/official-law-snapshot")
        data = response.json()
        assert response.status_code == 200
        assert data["procedure_candidate_count"] >= 1
        assert data["confirmed_reference_count"] >= 1
        assert data["unconfirmed_candidate_count"] >= 0
        assert data["latest_candidate_confirmed_at"] is not None
        assert data["confirmable_candidate_count"] >= 0
        assert data["raw_payload_storage_policy_ok"] is True
        assert data["raw_payload_storage_violation_count"] == 0
        assert SECRET_LIKE not in str(data)
    finally:
        _cleanup()


def test_seed_validation_script_accepts_safe_seed_and_rejects_raw_payload():
    tmp_dir = ROOT / "pytest-cache-files-phase30"
    tmp_dir.mkdir(exist_ok=True)
    safe = tmp_dir / "safe_seed.json"
    unsafe = tmp_dir / "unsafe_seed.json"
    try:
        safe.write_text(
            json.dumps(
                {
                    "items": [
                        {
                            "procedure_code": "PROJECT_BASIC_REVIEW",
                            "law_name": "TEST_PHASE27_MANUAL_LAW_DO_NOT_USE",
                            "article_title": "TEST_PHASE27_ARTICLE_TITLE_JSON",
                            "source_mode_detail": "official_seed_db",
                            "is_confirmed": True,
                            "confirmation_note": "TEST reviewed",
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        assert validate_seed_file(safe) == []
        assert validate_seed_main(["--path", str(safe)]) == 0

        unsafe.write_text(
            json.dumps(
                {
                    "items": [
                        {
                            "procedure_code": "PROJECT_BASIC_REVIEW",
                            "law_name": "TEST_PHASE27_MANUAL_LAW_DO_NOT_USE",
                            "article_title": "TEST_PHASE27_ARTICLE_TITLE_JSON",
                            "source_mode_detail": "official_seed_db",
                            "raw_json": {"secret": SECRET_LIKE},
                            "is_confirmed": True,
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        errors = validate_seed_file(unsafe)
        assert any("forbidden raw payload" in error for error in errors)
        assert any("confirmed seed candidates require" in error for error in errors)
    finally:
        safe.unlink(missing_ok=True)
        unsafe.unlink(missing_ok=True)
        if tmp_dir.exists():
            tmp_dir.rmdir()
