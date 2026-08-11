from copy import deepcopy
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select

from app.core.database import SessionLocal
from app.main import app
from app.models import Law, LawAttachedTableEvidence
from app.services.analyzer import _validate_applicability_evidence
from app.services.attached_table_evidence_service import (
    parse_attached_table_payload,
    resolve_attached_table_evidence,
    sync_attached_table_evidence,
)
from app.services.rule_loader import load_yaml_rule

client = TestClient(app)
LAW_NAME = "PHASE48_TEST_LAW_DO_NOT_USE"
LAW_KEY = "PHASE48_TEST_KEY_DO_NOT_USE"


def _payload(mst="100", text="urban development scope"):
    return {"법령": {"별표": {"별표단위": [{
        "별표번호": "0001", "별표제목": "TEST TABLE DO NOT USE", "별표내용": text
    }]}}}


def _cleanup():
    with SessionLocal() as db:
        laws = list(db.scalars(select(Law).where(Law.law_key == LAW_KEY)).all())
        for law in laws:
            db.execute(delete(LawAttachedTableEvidence).where(LawAttachedTableEvidence.law_id == law.id))
            db.delete(law)
        db.commit()


def test_attached_table_parse_normalizes_content_and_provenance_fields():
    items = parse_attached_table_payload(_payload(text=" A\n  B "), "100", date(2025, 1, 1))
    assert len(items) == 1
    assert items[0].table_key == "table:0001"
    assert items[0].normalized_text == "A B"
    assert items[0].mst == "100"


def test_sync_is_idempotent_and_as_of_selects_correct_version():
    _cleanup()
    try:
        with SessionLocal() as db:
            law = Law(law_name=LAW_NAME, law_key=LAW_KEY, source="TEST", mapping_status="verified")
            db.add(law); db.flush()
            sync_attached_table_evidence(db, law, _payload("100", "old"), "100", date(2025, 1, 1))
            sync_attached_table_evidence(db, law, _payload("100", "old updated"), "100", date(2025, 1, 1))
            sync_attached_table_evidence(db, law, _payload("200", "current"), "200", date(2026, 1, 1))
            sync_attached_table_evidence(db, law, _payload("300", "future"), "300", date(2027, 1, 1))
            db.commit()
            assert db.scalar(select(func.count()).select_from(LawAttachedTableEvidence).where(LawAttachedTableEvidence.law_id == law.id)) == 3
            assert resolve_attached_table_evidence(db, LAW_NAME, "0001", date(2025, 6, 1)).mst == "100"
            assert resolve_attached_table_evidence(db, LAW_NAME, "0001", date(2026, 6, 1)).mst == "200"
            assert resolve_attached_table_evidence(db, LAW_NAME, "0001", date(2024, 1, 1)) is None
    finally:
        _cleanup()


def test_verified_threshold_requires_valid_operator_unit_and_category():
    rules = deepcopy(load_yaml_rule("assessment_applicability_evidence.yaml"))
    item = rules["assessment_evidence"][0]
    item["applicability_status"] = "verified"
    item["threshold_status"] = "verified"
    item["threshold_evidence"] = {
        "value": 1, "unit": "TEST_UNIT", "operator": "gte",
        "project_category": "TEST_CATEGORY", "law_name": "TEST_LAW",
        "source_locator": "TEST_TABLE", "effective_date": "2099-01-01",
    }
    assert _validate_applicability_evidence(rules)[item["assessment_code"]]["threshold_status"] == "verified"
    item["threshold_evidence"]["operator"] = "approximately"
    with pytest.raises(ValueError, match="operator"):
        _validate_applicability_evidence(rules)


def test_placeholder_threshold_cannot_become_automatic_outcome():
    response = client.post("/api/analyze", json={
        "project_name": "TEST", "location": "TEST", "area_square_meters": 1,
        "implementation_method": "mixed", "implementer_type": "public_private_spc",
        "local_government": "TEST", "assessment_inputs": {
            "environmental_assessment_context": {}, "traffic_assessment_context": {},
            "disaster_review_context": {}, "underground_safety_context": {},
            "urban_planning_review_context": {}, "landscape_review_context": {},
            "educational_environment_context": {}, "buried_heritage_context": {},
        }
    })
    assert response.status_code == 200
    items = response.json()["assessments"]
    assert all(item["determination_status"] == "UNRESOLVED" for item in items)
    assert not any(item["verified_outcome"] in {"REQUIRED", "NOT_REQUIRED"} for item in items)


def test_local_rule_required_is_explicit_and_backward_compatible():
    response = client.post("/api/analyze", json={
        "project_name": "TEST", "location": "TEST", "area_square_meters": 1,
        "implementation_method": "replotting", "implementer_type": "private",
        "local_government": "TEST"
    })
    assert response.status_code == 200
    local = [x for x in response.json()["assessments"] if x["local_rule_required"]]
    assert {x["assessment_code"] for x in local} == {"URBAN_PLANNING_COMMITTEE_REVIEW", "LANDSCAPE_REVIEW"}
    assert all(x["determination_status"] == "NEED_MORE_INFO" for x in local)


def test_evidence_provenance_contains_no_secret_material():
    rules = repr(load_yaml_rule("assessment_applicability_evidence.yaml"))
    assert "OC=" not in rules
    assert "MOLEG_API_KEY" not in rules
