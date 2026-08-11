from copy import deepcopy
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.core.database import SessionLocal
from app.main import app
from app.models import Law, LawArticle, LawArticleVersion, ProcedureLegalReference
from app.schemas.analyze import AnalyzeRequest
from app.services.analyzer import _validate_assessment_rules, analyze_project
from app.services.rule_loader import load_yaml_rule


client = TestClient(app)
TEST_LAW_KEY = "TEST_PHASE46_LAW_DO_NOT_USE"
TEST_ASSESSMENT_CODE = "ENVIRONMENTAL_IMPACT_ASSESSMENT"


def _payload(**overrides):
    payload = {
        "project_name": "TEST_PHASE46_PROJECT_DO_NOT_USE",
        "location": "TEST_LOCATION_DO_NOT_USE",
        "area_square_meters": 1,
        "implementation_method": "mixed",
        "implementer_type": "public_private_spc",
        "local_government": "TEST_LOCAL_GOVERNMENT_DO_NOT_USE",
    }
    payload.update(overrides)
    return payload


def _delete_fixture() -> None:
    with SessionLocal() as db:
        law_ids = list(db.scalars(select(Law.id).where(Law.law_key == TEST_LAW_KEY)).all())
        if not law_ids:
            return
        article_ids = list(db.scalars(select(LawArticle.id).where(LawArticle.law_id.in_(law_ids))).all())
        db.execute(delete(ProcedureLegalReference).where(ProcedureLegalReference.law_id.in_(law_ids)))
        if article_ids:
            db.execute(delete(LawArticleVersion).where(LawArticleVersion.law_article_id.in_(article_ids)))
            db.execute(delete(LawArticle).where(LawArticle.id.in_(article_ids)))
        db.execute(delete(Law).where(Law.id.in_(law_ids)))
        db.commit()


def _create_verified_fixture() -> None:
    with SessionLocal() as db:
        law = Law(
            law_name="TEST_PHASE46_LAW_DO_NOT_USE",
            law_key=TEST_LAW_KEY,
            source="TEST_SOURCE_DO_NOT_USE",
            mapping_status="verified",
        )
        db.add(law)
        db.flush()
        article = LawArticle(
            law_id=law.id,
            article_key="TEST_PHASE46_ARTICLE_DO_NOT_USE",
            article_number_text="TEST_ARTICLE_DO_NOT_USE",
            article_title="TEST_ARTICLE_TITLE_DO_NOT_USE",
            mapping_status="verified",
        )
        db.add(article)
        db.flush()
        db.add_all([
            LawArticleVersion(
                law_article_id=article.id,
                effective_date=date(2099, 1, 1),
                article_text="TEST_CURRENT_TEXT_DO_NOT_USE",
                source="TEST_SOURCE_DO_NOT_USE",
                version_status="verified",
                raw_payload_json={"fixture": "TEST_ONLY_DO_NOT_USE"},
            ),
            LawArticleVersion(
                law_article_id=article.id,
                effective_date=date(2100, 1, 1),
                article_text="TEST_SCHEDULED_TEXT_DO_NOT_USE",
                source="TEST_SOURCE_DO_NOT_USE",
                version_status="verified",
                raw_payload_json={"fixture": "TEST_ONLY_DO_NOT_USE"},
            ),
        ])
        db.add(ProcedureLegalReference(
            step_code=TEST_ASSESSMENT_CODE,
            law_id=law.id,
            law_article_id=article.id,
            reference_status="verified",
            placeholder="TEST_VERIFIED_REFERENCE_FIXTURE_DO_NOT_USE",
            notes_json={"reference_quality": "verified", "fixture": "TEST_ONLY_DO_NOT_USE"},
        ))
        db.commit()


def test_placeholder_assessments_need_more_info_without_fabricated_thresholds():
    response = client.post("/api/analyze", json=_payload())
    assert response.status_code == 200
    assessments = response.json()["assessments"]

    assert len(assessments) == 8
    assert all(item["determination_status"] == "NEED_MORE_INFO" for item in assessments)
    assert all(item["missing_inputs"] for item in assessments)
    assert all(item["threshold"] == "TODO_PLACEHOLDER_DO_NOT_USE_AS_CRITERIA" for item in assessments)
    assert all(item["legal_references"] == [] for item in assessments)
    assert {item["legal_basis_status"] for item in assessments} == {"placeholder", "unresolved"}


def test_complete_context_does_not_promote_unverified_rule_to_required():
    rules = load_yaml_rule("assessment_rules.yaml")
    inputs = {
        key: {"fixture": "TEST_CONTEXT_DO_NOT_USE"}
        for item in rules["assessment_items"] for key in item["required_inputs"]
    }
    response = client.post("/api/analyze", json=_payload(assessment_inputs=inputs))
    assert response.status_code == 200

    for item in response.json()["assessments"]:
        assert item["missing_inputs"] == []
        assert item["determination_status"] == "UNRESOLVED"
        assert item["status"] == "?? ?? ??"


def test_verified_stored_assessment_reference_uses_as_of_article_version():
    _delete_fixture()
    _create_verified_fixture()
    try:
        response = client.post(
            "/api/analyze",
            json=_payload(
                as_of="2099-06-15",
                assessment_inputs={"environmental_assessment_context": {"fixture": "TEST_ONLY"}},
            ),
        )
        assert response.status_code == 200
        item = next(
            value for value in response.json()["assessments"]
            if value["assessment_code"] == TEST_ASSESSMENT_CODE
        )

        assert item["legal_basis_status"] == "verified"
        assert item["determination_status"] == "UNRESOLVED"
        assert item["as_of"] == "2099-06-15"
        assert len(item["legal_references"]) == 1
        reference = item["legal_references"][0]
        assert reference["reference_quality"] == "verified"
        assert reference["current_version"]["effective_date"] == "2099-01-01"
        assert {v["temporal_status"] for v in reference["versions"]} == {"current", "scheduled"}
    finally:
        _delete_fixture()


def test_assessment_regression_matrix_is_stable_across_existing_branches():
    variants = [
        ("expropriation_or_use", "public"),
        ("replotting", "private"),
        ("mixed", "public_private_spc"),
    ]
    snapshots = []
    for method, implementer in variants:
        result = analyze_project(AnalyzeRequest(**_payload(
            implementation_method=method, implementer_type=implementer
        )))
        snapshots.append([
            (item.assessment_code, item.determination_status, item.legal_basis_status)
            for item in result.assessments
        ])

    assert snapshots[0] == snapshots[1] == snapshots[2]
    assert len(snapshots[0]) == 8


def test_analyze_request_without_assessment_inputs_is_backward_compatible():
    response = client.post("/api/analyze", json=_payload())
    assert response.status_code == 200
    data = response.json()

    assert "procedures" in data
    assert "standard_procedure_graph" in data
    assert "assessments" in data
    assert all("name" in item and "status" in item and "threshold" in item for item in data["assessments"])


def test_assessment_rule_validation_rejects_duplicate_codes():
    rules = deepcopy(load_yaml_rule("assessment_rules.yaml"))
    rules["assessment_items"][1]["assessment_code"] = rules["assessment_items"][0]["assessment_code"]

    with pytest.raises(ValueError, match="assessment codes must be unique"):
        _validate_assessment_rules(rules)


def test_assessment_rule_validation_rejects_verified_placeholder_basis():
    rules = deepcopy(load_yaml_rule("assessment_rules.yaml"))
    rules["assessment_items"][0]["legal_basis_status"] = "verified"

    with pytest.raises(ValueError, match="placeholder legal basis cannot be marked verified"):
        _validate_assessment_rules(rules)
