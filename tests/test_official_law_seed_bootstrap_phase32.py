from __future__ import annotations

import json
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.core.database import SessionLocal
from app.main import app
from app.models import OfficialLawArticleRecord, OfficialLawDocument, OfficialLawIngestRun, OfficialLawSourceEvidence, ProcedureOfficialArticleCandidate
from app.services.official_law_seed_bootstrap_service import import_official_law_seed_directory, validate_official_law_seed_directory

client = TestClient(app)
LAW_KEY = "dummy_phase32_law_do_not_use"
LAW_NAME = "DUMMY_PHASE32_LAW_DO_NOT_USE"
ARTICLE_NO = "DUMMY_PHASE32_ARTICLE_NO_DO_NOT_USE"
ARTICLE_ANCHOR = "dummy-phase32-anchor"
SECRET = "TEST_PHASE32_SECRET_DO_NOT_USE"
TMP_ROOT = Path("tests") / ".tmp_phase32"


def _seed_yaml(article_extra: str = "", source_url: str = "https://example.test/official-source") -> str:
    return f"""
seed_version: 1
law_key: {LAW_KEY}
law_name: {LAW_NAME}
law_type: other
source:
  source_type: official_manual
  source_name: DUMMY_PHASE32_SOURCE_DO_NOT_USE
  source_url_optional: {source_url}
  retrieved_at_optional: 2099-01-01
  verified_by_optional: DUMMY_REVIEWER_DO_NOT_USE
  verification_note_optional: DUMMY review note only.
articles:
  - article_key: dummy_phase32_article_key_do_not_use
    article_no: {ARTICLE_NO}
    article_title: DUMMY_PHASE32_ARTICLE_TITLE_DO_NOT_USE
    article_anchor: {ARTICLE_ANCHOR}
    sanitized_summary: DUMMY sanitized summary for Project basic review only, not article body.
    status: unknown
    procedure_codes:
      - PROJECT_BASIC_REVIEW
    tags:
      - dummy
    source_mode_detail: official_seed_db
    confidence: 0.9
    is_confirmed: true
    confirmation_note: DUMMY confirmation only.
{article_extra}
"""


def _write_seed_dir(content: str | None = None) -> Path:
    seed_dir = TMP_ROOT / uuid.uuid4().hex
    seed_dir.mkdir(parents=True, exist_ok=True)
    (seed_dir / "dummy.seed.yaml").write_text(content if content is not None else _seed_yaml(), encoding="utf-8")
    return seed_dir


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


def test_seed_yaml_schema_validation_success():
    seed_dir = _write_seed_dir()
    try:
        report = validate_official_law_seed_directory(seed_dir=seed_dir, include_examples=False)
        assert report.status == "ok"
        assert report.total_files == 1
        assert report.total_articles == 1
        assert report.confirmed_articles == 1
        assert report.raw_payload_policy_ok is True
        assert report.secret_exposed is False
    finally:
        shutil.rmtree(seed_dir, ignore_errors=True)


def test_empty_official_seed_files_are_empty_valid():
    report = validate_official_law_seed_directory(include_examples=False)
    assert report.status == "empty_valid"
    assert report.total_files == 3
    assert report.empty_files == 3
    assert report.total_articles == 0


def test_forbidden_field_fails_validation():
    seed_dir = _write_seed_dir(_seed_yaml(article_extra="    raw_payload: SHOULD_FAIL\n"))
    try:
        report = validate_official_law_seed_directory(seed_dir=seed_dir, include_examples=False)
        assert report.status == "failed"
        assert report.rejected_count == 1
        assert any("forbidden field raw_payload" in error for error in report.errors)
    finally:
        shutil.rmtree(seed_dir, ignore_errors=True)


def test_sensitive_query_parameter_fails_validation():
    seed_dir = _write_seed_dir(_seed_yaml(source_url="https://example.test/source?serviceKey=SHOULD_NOT_APPEAR"))
    try:
        report = validate_official_law_seed_directory(seed_dir=seed_dir, include_examples=False)
        assert report.status == "failed"
        assert any("sensitive query" in error for error in report.errors)
        dumped = json.dumps(report.to_dict(), ensure_ascii=False)
        assert SECRET not in dumped
    finally:
        shutil.rmtree(seed_dir, ignore_errors=True)


def test_dummy_example_seed_validation():
    report = validate_official_law_seed_directory(include_examples=True)
    assert report.rejected_count == 0
    assert any(item.is_example and item.status == "valid" for item in report.files)


def test_import_script_empty_seed_smoke():
    completed = subprocess.run([sys.executable, "-m", "scripts.import_official_law_seeds"], capture_output=True, text=True, check=False)
    assert completed.returncode == 0
    data = json.loads(completed.stdout)
    assert data["status"] == "ok"
    assert data["empty_files"] == 3
    assert data["articles_imported"] == 0
    assert data["raw_payload_policy_ok"] is True
    assert data["secret_exposed"] is False


def test_import_idempotency_and_candidate_priority_with_dummy_seed():
    _cleanup()
    seed_dir = _write_seed_dir()
    try:
        db = SessionLocal()
        try:
            first = import_official_law_seed_directory(db=db, seed_dir=seed_dir)
            second = import_official_law_seed_directory(db=db, seed_dir=seed_dir)
            assert first["articles_imported"] == 1
            assert second["articles_imported"] == 1
            articles = db.scalars(select(OfficialLawArticleRecord).join(OfficialLawDocument).where(OfficialLawDocument.law_id == LAW_KEY)).all()
            candidates = db.scalars(select(ProcedureOfficialArticleCandidate).where(ProcedureOfficialArticleCandidate.law_id == LAW_KEY)).all()
            assert len(articles) == 1
            assert len(candidates) == 1
            assert candidates[0].source_mode_detail == "official_seed_db"
            assert candidates[0].is_confirmed is True
        finally:
            db.close()

        response = client.post(
            "/api/analyze",
            json={
                "project_name": "Phase32 Dummy Seed",
                "location": "Test Location",
                "area_square_meters": 100000,
                "implementation_method": "expropriation_or_use",
                "implementer_type": "public",
                "local_government": "Test LG",
            },
        )
        assert response.status_code == 200
        data = response.json()
        step = next(item for item in data["procedures"] if item["step_code"] == "PROJECT_BASIC_REVIEW")
        assert len(data["procedures"]) == 13
        assert step["official_article_candidates"][0]["source_mode_detail"] == "official_seed_db"
        assert step["official_article_candidates"][0]["is_confirmed"] is True
    finally:
        _cleanup()
        shutil.rmtree(seed_dir, ignore_errors=True)


def test_seed_status_api_and_snapshot_include_seed_status():
    status = client.get("/api/legal-references/official-law-seeds/status")
    snapshot = client.get("/api/legal-references/official-law-snapshot")
    assert status.status_code == 200
    status_data = status.json()
    assert status_data["seed_directory_exists"] is True
    assert status_data["total_files"] == 3
    assert status_data["total_articles"] == 0
    assert status_data["raw_payload_policy_ok"] is True
    assert status_data["secret_exposed"] is False

    assert snapshot.status_code == 200
    snapshot_data = snapshot.json()
    assert snapshot_data["official_seed_files_count"] == 3
    assert snapshot_data["official_seed_articles_count"] == 0
    assert snapshot_data["official_seed_validation_status"] == "empty_valid"
    assert snapshot_data["raw_payload_storage_policy_ok"] is True


def test_validate_script_outputs_safe_summary():
    completed = subprocess.run([sys.executable, "-m", "scripts.validate_official_law_seeds"], capture_output=True, text=True, check=False)
    assert completed.returncode == 0
    data = json.loads(completed.stdout)
    assert data["status"] == "empty_valid"
    assert data["secret_exposed"] is False
    assert data["raw_payload_policy_ok"] is True
    assert "raw_json" not in completed.stdout
    assert SECRET not in completed.stdout


def teardown_module():
    shutil.rmtree(TMP_ROOT, ignore_errors=True)

