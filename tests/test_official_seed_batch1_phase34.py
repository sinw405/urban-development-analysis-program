from __future__ import annotations

import json
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.services.official_law_seed_bootstrap_service import plan_official_law_seed_import, validate_official_law_seed_directory
from app.services.official_seed_intake_service import generate_official_seed_from_intake, validate_official_seed_intake

client = TestClient(app)
FIXTURE_DIR = Path("tests/fixtures/official_seed_intake")
SECRET = "TEST_PHASE34_SECRET_DO_NOT_USE"


def _workspace_tmp_dir() -> Path:
    path = Path("tests/.tmp_phase34") / uuid.uuid4().hex
    path.mkdir(parents=True, exist_ok=True)
    return path


def _run_module(*args: str) -> dict:
    completed = subprocess.run([sys.executable, "-m", *args], capture_output=True, text=True, check=False)
    assert completed.returncode == 0, completed.stderr + completed.stdout
    assert SECRET not in completed.stdout
    return json.loads(completed.stdout)


def test_phase34_default_source_material_template_only():
    data = _run_module("scripts.validate_official_seed_intake")
    assert data["status"] == "template_only"
    assert data["files_scanned"] == 1
    assert data["template_files"] == 1
    assert data["source_rows"] == 0
    assert data["ready_for_seed_generation"] is False
    assert data["raw_payload_policy_ok"] is True
    assert data["secret_exposed"] is False


def test_phase34_forbidden_raw_field_intake_fails():
    tmp_path = _workspace_tmp_dir()
    try:
        intake = tmp_path / "bad.csv"
        intake.write_text(
            "law_key,law_name,law_type,article_no,article_title,article_anchor,official_source_url,sanitized_summary,procedure_codes,status,confidence,is_confirmed,verification_note,raw_payload\n"
            "dummy_law,Dummy Law,other,DUMMY-RAW,Dummy,dummy#raw,https://example.invalid/dummy,summary,PROJECT_BASIC_REVIEW,unknown,0.5,false,note,forbidden\n",
            encoding="utf-8",
        )
        report = validate_official_seed_intake(tmp_path)
        assert report.status == "failed"
        assert report.rejected_rows == 1
        assert report.raw_payload_policy_ok is False
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_phase34_sensitive_url_and_missing_confirmation_note_fail():
    tmp_path = _workspace_tmp_dir()
    try:
        intake = tmp_path / "bad.csv"
        intake.write_text(
            "law_key,law_name,law_type,article_no,article_title,article_anchor,official_source_url,sanitized_summary,procedure_codes,status,confidence,is_confirmed,verification_note\n"
            "dummy_law,Dummy Law,other,DUMMY-SECRET,Dummy,dummy#secret,https://example.invalid/dummy?serviceKey=hidden,summary,PROJECT_BASIC_REVIEW,unknown,0.5,true,\n",
            encoding="utf-8",
        )
        report = validate_official_seed_intake(tmp_path)
        assert report.status == "failed"
        assert report.rejected_rows == 1
        assert report.secret_exposed is True
        assert any("sensitive query parameter" in error for error in report.errors)
        assert any("confirmed rows require" in error for error in report.errors)
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_phase34_dummy_intake_validation_and_dry_run_success():
    data = _run_module("scripts.validate_official_seed_intake", "--path", str(FIXTURE_DIR))
    assert data["status"] == "ok"
    assert data["source_rows"] == 1
    assert data["valid_rows"] == 1
    assert data["ready_for_seed_generation"] is True
    assert data["raw_payload_policy_ok"] is True
    assert data["secret_exposed"] is False
    tmp_path = _workspace_tmp_dir()
    try:
        dry_run = _run_module("scripts.generate_official_seed_from_intake", "--path", str(FIXTURE_DIR), "--seed-dir", str(tmp_path / "seeds"), "--dry-run")
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)
    assert dry_run["status"] == "dry_run"
    assert dry_run["seed_files_planned"] == 1
    assert dry_run["articles_planned"] == 1
    assert dry_run["seed_files_written"] == 0


def test_phase34_apply_without_source_rows_does_not_modify_default_seed():
    result = _run_module("scripts.generate_official_seed_from_intake", "--apply")
    assert result["status"] == "template_only"
    assert result["source_rows"] == 0
    assert result["seed_files_written"] == 0


def test_phase34_dummy_intake_generation_seed_validation_and_import_dry_run():
    tmp_path = _workspace_tmp_dir()
    try:
        seed_dir = tmp_path / "seeds"
        result = generate_official_seed_from_intake(source_dir=FIXTURE_DIR, seed_dir=seed_dir, apply=True)
        assert result["status"] == "ok"
        assert result["seed_files_written"] == 1
        generated = seed_dir / "dummy_official_batch1_law.seed.yaml"
        assert generated.exists()
        content = generated.read_text(encoding="utf-8")
        assert "DUMMY-BATCH1-001" in content
        assert "raw_payload" not in content
        assert SECRET not in content
        validation = validate_official_law_seed_directory(seed_dir=seed_dir, include_examples=False)
        assert validation.status == "ok"
        assert validation.total_articles == 1
        import_plan = plan_official_law_seed_import(seed_dir=seed_dir)
        assert import_plan["status"] == "dry_run"
        assert import_plan["articles_import_planned"] == 1
        assert import_plan["candidates_create_planned"] == 1
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_phase34_status_snapshot_and_analyze_include_intake_state():
    status = client.get("/api/legal-references/official-law-seeds/status")
    snapshot = client.get("/api/legal-references/official-law-snapshot")
    assert status.status_code == 200
    status_data = status.json()
    assert status_data["source_material_directory_exists"] is True
    assert status_data["source_intake_template_exists"] is True
    assert status_data["source_intake_status"] == "template_only"
    assert status_data["ready_for_seed_generation"] is False
    assert status_data["batch1_policy_exists"] is True
    assert status_data["batch1_apply_supported"] is True
    assert status_data["raw_payload_policy_ok"] is True
    assert status_data["secret_exposed"] is False
    assert snapshot.status_code == 200
    snapshot_data = snapshot.json()
    assert snapshot_data["official_seed_source_material_directory_exists"] is True
    assert snapshot_data["official_seed_source_intake_status"] == "template_only"
    assert snapshot_data["official_seed_source_intake_rows"] == 0
    assert snapshot_data["official_seed_ready_for_seed_generation"] is False
    assert snapshot_data["official_seed_batch1_policy_exists"] is True
    assert snapshot_data["raw_payload_storage_policy_ok"] is True
    response = client.post(
        "/api/analyze",
        json={
            "project_name": "Phase34 Source Missing Smoke",
            "location": "Test Location",
            "area_square_meters": 100000,
            "implementation_method": "expropriation_or_use",
            "implementer_type": "public",
            "local_government": "Test LG",
        },
    )
    assert response.status_code == 200
    assert len(response.json()["procedures"]) == 13
