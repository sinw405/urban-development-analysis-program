from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.analyze import AnalyzeRequest
from app.services.analyzer import (
    _validate_applicability_evidence,
    analyze_project,
)
from app.services.rule_loader import load_yaml_rule


client = TestClient(app)


def _payload(**overrides):
    payload = {
        "project_name": "PHASE47_TEST_DO_NOT_USE",
        "location": "TEST_LOCATION_DO_NOT_USE",
        "area_square_meters": 1000,
        "implementation_method": "expropriation_or_use",
        "implementer_type": "public",
        "local_government": "TEST_LOCAL_GOVERNMENT_DO_NOT_USE",
    }
    payload.update(overrides)
    return payload


def test_phase47_evidence_covers_all_assessments_without_verified_thresholds():
    rules = load_yaml_rule("assessment_applicability_evidence.yaml")
    by_code = _validate_applicability_evidence(rules)

    assert len(by_code) == 8
    assert {item["applicability_status"] for item in by_code.values()} == {
        "partial", "unresolved", "local_rule_required"
    }
    assert all(item["threshold_status"] == "placeholder" for item in by_code.values())
    assert all(item["evidence"] for item in by_code.values())
    assert all(source["source"] == "MOLEG_LIVE_PHASE47" for item in by_code.values() for source in item["evidence"])


def test_api_exposes_additive_evidence_and_keeps_old_fields():
    response = client.post("/api/analyze", json=_payload())
    assert response.status_code == 200
    assessments = response.json()["assessments"]

    assert len(assessments) == 8
    assert all("name" in item and "status" in item and "threshold" in item for item in assessments)
    assert all(item["applicability_evidence"] for item in assessments)
    assert all(item["determination_status"] == "NEED_MORE_INFO" for item in assessments)


def test_complete_context_still_cannot_promote_partial_or_expert_evidence():
    rules = load_yaml_rule("assessment_rules.yaml")
    inputs = {
        key: {"fixture": "TEST_CONTEXT_DO_NOT_USE"}
        for item in rules["assessment_items"] for key in item["required_inputs"]
    }
    result = analyze_project(AnalyzeRequest(**_payload(assessment_inputs=inputs)))

    assert all(item.missing_inputs == [] for item in result.assessments)
    assert all(item.determination_status == "UNRESOLVED" for item in result.assessments)
    assert all(item.threshold_status == "placeholder" for item in result.assessments)
    assert all(item.verified_outcome is None for item in result.assessments)


def test_verified_threshold_requires_complete_provenance():
    rules = deepcopy(load_yaml_rule("assessment_applicability_evidence.yaml"))
    rules["assessment_evidence"][0]["threshold_status"] = "verified"
    rules["assessment_evidence"][0]["threshold_evidence"] = {"value": 1}

    with pytest.raises(ValueError, match="complete evidence"):
        _validate_applicability_evidence(rules)


def test_evidence_rejects_missing_provenance_fields():
    rules = deepcopy(load_yaml_rule("assessment_applicability_evidence.yaml"))
    del rules["assessment_evidence"][0]["evidence"][0]["mst"]

    with pytest.raises(ValueError, match="missing provenance"):
        _validate_applicability_evidence(rules)


def test_evidence_has_no_secret_or_auth_url_material():
    raw = (load_yaml_rule("assessment_applicability_evidence.yaml"))
    rendered = repr(raw)
    assert "MOLEG_API_KEY" not in rendered
    assert "OC=" not in rendered
    assert "lawService.do?" not in rendered
