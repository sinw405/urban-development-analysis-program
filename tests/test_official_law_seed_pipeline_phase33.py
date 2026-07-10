from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.core.database import SessionLocal
from app.main import app
from app.models import OfficialLawArticleRecord, OfficialLawDocument, OfficialLawIngestRun, OfficialLawSourceEvidence, ProcedureOfficialArticleCandidate

client = TestClient(app)
FIXTURE_DIR = Path("tests/fixtures/official_law_seeds")
LAW_KEY = "dummy_official_law_seed_fixture"
LAW_NAME = "Dummy Official Law"
SECRET = "TEST_PHASE33_SECRET_DO_NOT_USE"


def _cleanup() -> None:
    db = SessionLocal()
    try:
        document_ids = list(db.scalars(select(OfficialLawDocument.id).where(OfficialLawDocument.law_id == LAW_KEY)).all())
        if document_ids:
            article_ids = list(db.scalars(select(OfficialLawArticleRecord.id).where(OfficialLawArticleRecord.document_id.in_(document_ids))).all())
            if article_ids:
                db.execute(delete(ProcedureOfficialArticleCandidate).where(ProcedureOfficialArticleCandidate.article_id.in_(article_ids)))
                db.execute(delete(OfficialLawArticleRecord).where(OfficialLawArticleRecord.id.in_(article_ids)))
            db.execute(delete(OfficialLawDocument).where(OfficialLawDocument.id.in_(document_ids)))
        run_ids = list(db.scalars(select(OfficialLawIngestRun.id).where(OfficialLawIngestRun.query == LAW_NAME)).all())
        if run_ids:
            db.execute(delete(OfficialLawSourceEvidence).where(OfficialLawSourceEvidence.ingest_run_id.in_(run_ids)))
            db.execute(delete(OfficialLawIngestRun).where(OfficialLawIngestRun.id.in_(run_ids)))
        db.commit()
    finally:
        db.close()


def _run_module(*args: str) -> dict:
    completed = subprocess.run([sys.executable, "-m", *args], capture_output=True, text=True, check=False)
    assert completed.returncode == 0, completed.stderr + completed.stdout
    assert SECRET not in completed.stdout
    return json.loads(completed.stdout)


def test_phase33_validation_path_option_and_dummy_fixture_success():
    data = _run_module("scripts.validate_official_law_seeds", "--path", str(FIXTURE_DIR))
    assert data["path"] == str(FIXTURE_DIR)
    assert data["status"] == "ok"
    assert data["total_files"] == 1
    assert data["total_articles"] == 2
    assert data["confirmed_articles"] == 1
    assert data["unconfirmed_articles"] == 1
    assert data["raw_payload_policy_ok"] is True
    assert data["secret_exposed"] is False


def test_phase33_import_dry_run_path_option_does_not_write_db():
    _cleanup()
    data = _run_module("scripts.import_official_law_seeds", "--path", str(FIXTURE_DIR), "--dry-run")
    assert data["status"] == "dry_run"
    assert data["files_imported_planned"] == 1
    assert data["articles_import_planned"] == 2
    assert data["candidates_create_planned"] == 2
    assert data["candidates_confirm_planned"] == 1
    assert data["candidates_unconfirmed_planned"] == 1
    db = SessionLocal()
    try:
        assert db.scalar(select(OfficialLawDocument).where(OfficialLawDocument.law_id == LAW_KEY)) is None
    finally:
        db.close()


def test_phase33_dummy_seed_import_idempotency_candidates_and_no_raw_storage():
    _cleanup()
    try:
        first = _run_module("scripts.import_official_law_seeds", "--path", str(FIXTURE_DIR))
        second = _run_module("scripts.import_official_law_seeds", "--path", str(FIXTURE_DIR))
        assert first["status"] == "ok"
        assert first["articles_imported"] == 2
        assert first["candidates_created"] == 2
        assert first["candidates_confirmed"] == 1
        assert first["candidates_unconfirmed"] == 1
        assert second["status"] == "ok"
        db = SessionLocal()
        try:
            documents = db.scalars(select(OfficialLawDocument).where(OfficialLawDocument.law_id == LAW_KEY)).all()
            articles = db.scalars(select(OfficialLawArticleRecord).join(OfficialLawDocument).where(OfficialLawDocument.law_id == LAW_KEY)).all()
            candidates = db.scalars(select(ProcedureOfficialArticleCandidate).where(ProcedureOfficialArticleCandidate.law_id == LAW_KEY)).all()
            evidence = db.scalars(select(OfficialLawSourceEvidence).join(OfficialLawIngestRun).where(OfficialLawIngestRun.query == LAW_NAME)).all()
            assert len(documents) == 1
            assert len(articles) == 2
            assert len(candidates) == 2
            assert sum(1 for item in candidates if item.is_confirmed) == 1
            assert sum(1 for item in candidates if not item.is_confirmed) == 1
            dumped = json.dumps([item.sanitized_summary_json for item in evidence], ensure_ascii=False)
            assert "raw_payload" not in dumped
            assert "raw_json" not in dumped
            assert "raw_xml" not in dumped
            assert "full_text" not in dumped
            assert SECRET not in dumped
        finally:
            db.close()
    finally:
        _cleanup()


def test_phase33_analyze_uses_confirmed_official_seed_db_first():
    _cleanup()
    try:
        _run_module("scripts.import_official_law_seeds", "--path", str(FIXTURE_DIR))
        response = client.post(
            "/api/analyze",
            json={
                "project_name": "Phase33 Dummy Seed Analyze",
                "location": "Test Location",
                "area_square_meters": 100000,
                "implementation_method": "expropriation_or_use",
                "implementer_type": "public",
                "local_government": "Test LG",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["procedures"]) == 13
        basic = next(step for step in data["procedures"] if step["step_code"] == "PROJECT_BASIC_REVIEW")
        zone = next(step for step in data["procedures"] if step["step_code"] == "ZONE_DESIGNATION_REVIEW")
        assert basic["official_article_candidates"][0]["source_mode_detail"] == "official_seed_db"
        assert basic["official_article_candidates"][0]["is_confirmed"] is True
        assert basic["official_article_candidates"][0]["article_no"] == "DUMMY-001"
        assert zone["official_article_candidates"][0]["source_mode_detail"] == "official_seed_db"
        assert zone["official_article_candidates"][0]["is_confirmed"] is False
        urban_development_law_name = "\ub3c4\uc2dc\uac1c\ubc1c\ubc95"
        assert all(urban_development_law_name not in json.dumps(candidate, ensure_ascii=False) for candidate in basic["official_article_candidates"])
    finally:
        _cleanup()


def test_phase33_status_and_snapshot_authoring_readiness():
    status = client.get("/api/legal-references/official-law-seeds/status")
    snapshot = client.get("/api/legal-references/official-law-snapshot")
    assert status.status_code == 200
    status_data = status.json()
    assert status_data["ready_for_manual_authoring"] is True
    assert status_data["authoring_checklist_exists"] is True
    assert status_data["review_manifest_template_exists"] is True
    assert status_data["dry_run_supported"] is True
    assert status_data["fixture_validation_supported"] is True
    assert status_data["unconfirmed_seed_articles"] == 0
    assert status_data["raw_payload_policy_ok"] is True
    assert status_data["secret_exposed"] is False
    assert snapshot.status_code == 200
    snapshot_data = snapshot.json()
    assert snapshot_data["official_seed_ready_for_manual_authoring"] is True
    assert snapshot_data["official_seed_authoring_checklist_exists"] is True
    assert snapshot_data["official_seed_review_manifest_template_exists"] is True
    assert snapshot_data["official_seed_dry_run_supported"] is True
    assert snapshot_data["official_seed_fixture_validation_supported"] is True
    assert snapshot_data["official_seed_unconfirmed_count"] == 0
    assert snapshot_data["raw_payload_storage_policy_ok"] is True


def test_phase33_empty_default_seed_behavior_is_preserved():
    data = _run_module("scripts.validate_official_law_seeds")
    assert data["status"] == "empty_valid"
    assert data["total_files"] == 3
    assert data["empty_files"] == 3
    assert data["total_articles"] == 0
