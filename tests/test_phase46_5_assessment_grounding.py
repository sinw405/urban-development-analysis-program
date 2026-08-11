from datetime import date

import pytest
from sqlalchemy import delete, func, select

from app.core.database import SessionLocal
from app.models import Law, LawArticle, LawArticleVersion, ProcedureLegalReference
from app.schemas.analyze import AssessmentItem
from app.services import assessment_reference_seed_service as seed_service
from app.services.analyzer import _validate_assessment_rules
from app.services.legal_reference_service import finalize_assessment_determination
from scripts.phase46_5_assessment_live_verify import render_report


TEST_LAW_KEY = "TEST_PHASE46_5_LAW_DO_NOT_USE"
TEST_CODE = "TEST_PHASE46_5_ASSESSMENT_DO_NOT_USE"
TEST_SOURCE = "TEST_MOLEG_SOURCE_DO_NOT_USE"


def _cleanup():
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


def _create_fixture():
    with SessionLocal() as db:
        law = Law(law_name="TEST_LAW_DO_NOT_USE", law_key=TEST_LAW_KEY, source="TEST", mapping_status="verified")
        db.add(law); db.flush()
        article = LawArticle(
            law_id=law.id,
            article_key="TEST_ARTICLE_KEY_DO_NOT_USE",
            article_number_text="TEST_ARTICLE_NUMBER_DO_NOT_USE",
            article_title="TEST_VERIFIED_TITLE_DO_NOT_USE",
            mapping_status="verified",
        )
        db.add(article); db.flush()
        db.add(LawArticleVersion(
            law_article_id=article.id,
            effective_date=date(2099, 1, 1),
            article_text="TEST_EVIDENCE_TERM_DO_NOT_USE",
            source=TEST_SOURCE,
            version_status="current",
            raw_payload_json=None,
        ))
        db.commit()


def _seed_config():
    return {"references": [{
        "assessment_code": TEST_CODE,
        "law_key": TEST_LAW_KEY,
        "article_number_text": "TEST_ARTICLE_NUMBER_DO_NOT_USE",
        "article_title": "TEST_VERIFIED_TITLE_DO_NOT_USE",
        "evidence_terms": ["TEST_EVIDENCE_TERM_DO_NOT_USE"],
        "source": "TEST_SOURCE_DO_NOT_USE",
        "verified_version_sources": [TEST_SOURCE],
        "verified_at": "2099-01-02",
    }]}


def test_production_seed_is_idempotent_and_keeps_applicability_unresolved(monkeypatch):
    _cleanup(); _create_fixture()
    monkeypatch.setattr(seed_service, "load_yaml_rule", lambda _: _seed_config())
    try:
        with SessionLocal() as db:
            first = seed_service.apply_assessment_reference_seeds(db, apply=True, as_of=date(2099, 6, 1))
        with SessionLocal() as db:
            second = seed_service.apply_assessment_reference_seeds(db, apply=True, as_of=date(2099, 6, 1))
            count = db.scalar(select(func.count()).select_from(ProcedureLegalReference).where(ProcedureLegalReference.step_code == TEST_CODE))
            reference = db.scalar(select(ProcedureLegalReference).where(ProcedureLegalReference.step_code == TEST_CODE))

        assert first.created_count == 1
        assert second.existing_count == 1
        assert count == 1
        assert reference.reference_status == "verified"
        assert reference.notes_json["reference_quality"] == "verified"
        assert reference.notes_json["applicability_status"] == "unresolved"
        assert reference.notes_json["threshold_status"] == "placeholder"
    finally:
        _cleanup()


def test_seed_refuses_missing_as_of_version(monkeypatch):
    _cleanup(); _create_fixture()
    monkeypatch.setattr(seed_service, "load_yaml_rule", lambda _: _seed_config())
    try:
        with SessionLocal() as db:
            result = seed_service.apply_assessment_reference_seeds(db, apply=True, as_of=date(2098, 1, 1))
        assert result.created_count == 0
        assert result.unresolved_count == 1
        assert result.items[0].errors == ["as_of_version_missing"]
    finally:
        _cleanup()


def test_legal_basis_verified_does_not_verify_applicability():
    item = AssessmentItem(
        assessment_code="TEST_DO_NOT_USE", name="TEST", status="TEST", threshold="TEST",
        legal_basis="TEST", required_action="TEST", legal_basis_status="verified",
        applicability_status="unresolved", threshold_status="placeholder", missing_inputs=[],
    )
    finalize_assessment_determination(item)
    assert item.determination_status == "UNRESOLVED"


def test_both_verified_can_return_configured_outcome():
    item = AssessmentItem(
        assessment_code="TEST_DO_NOT_USE", name="TEST", status="TEST", threshold="TEST",
        legal_basis="TEST", required_action="TEST", legal_basis_status="verified",
        applicability_status="verified", threshold_status="not_applicable", verified_outcome="REQUIRED",
        missing_inputs=[], requires_expert_review=False,
    )
    finalize_assessment_determination(item)
    assert item.determination_status == "REQUIRED"


def test_verified_applicability_rejects_placeholder_threshold():
    rules = {"assessment_items": [{
        "assessment_code": "TEST_DO_NOT_USE", "required_inputs": [],
        "legal_basis": "TEST_VERIFIED_BASIS_DO_NOT_USE", "legal_basis_status": "verified",
        "applicability_status": "verified", "threshold_status": "placeholder",
        "verified_outcome": "REQUIRED",
    }]}
    with pytest.raises(ValueError, match="cannot use an unresolved threshold"):
        _validate_assessment_rules(rules)


def test_live_runner_report_never_renders_secret_value():
    rendered = render_report({"moleg_configured": True, "secret_exposed": False, "FINAL RESULT": "PASS"})
    assert "MOLEG_API_KEY" not in rendered
    assert "OC=" not in rendered
    assert '"secret_exposed": false' in rendered
