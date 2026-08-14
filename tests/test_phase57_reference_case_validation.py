from pathlib import Path

import pytest

from app.schemas.analyze import AnalyzeResponse
from app.schemas.reference_validation import (
    ExpectedAssessment,
    ExpectedLegalReference,
    ExpectedStep,
    MatchStatus,
    ReferenceCaseValidationInput,
)
from app.services.analyzer import analyze_project
from app.services.reference_case_validation_service import load_reference_case, validate_reference_case


FIXTURE = Path(__file__).parent / "fixtures" / "phase57_reference_case_sample.json"


def result():
    reference = load_reference_case(FIXTURE, allow_test_fixture=True)
    return analyze_project(reference.project_input)


def reference_for(actual, **changes):
    values = dict(
        fixture_id="PHASE57_TEST_SAMPLE_FIXTURE_DO_NOT_USE",
        reference_case_name="TEST/SAMPLE/FIXTURE validation case",
        data_classification="TEST_SAMPLE_FIXTURE",
        source_note="TEST/SAMPLE/FIXTURE only; not real-project evidence.",
        project_input=load_reference_case(FIXTURE, allow_test_fixture=True).project_input,
        expected_steps=[
            ExpectedStep(
                step_code=step.step_code,
                step_name=step.step_name,
                required_documents=list(step.required_documents),
                related_agencies=list(step.related_agencies),
                estimated_duration=step.estimated_duration,
            )
            for step in actual.procedures
        ],
        expected_assessments=[
            ExpectedAssessment(
                assessment_code=item.assessment_code,
                status=item.status,
                required_action=item.required_action,
            )
            for item in actual.assessments if item.assessment_code
        ],
        expected_legal_references=[],
    )
    values.update(changes)
    return ReferenceCaseValidationInput(**values)


def statuses(report, category):
    return [item.status for item in report.items if item.category == category]


def test_complete_match_and_match_rate_formula():
    actual = result()
    report = validate_reference_case(reference_for(actual), actual)
    assert report.procedure_match_rate.matched == len(actual.procedures)
    assert report.procedure_match_rate.verified_expected == len(actual.procedures)
    assert report.procedure_match_rate.rate_percent == 100.0
    assert report.procedure_match_rate.formula == "matched / verified_expected * 100; UNVERIFIED items excluded"
    assert not report.mismatches


def test_missing_and_extra_procedure_are_reported_without_changing_engine():
    actual = result()
    expected = reference_for(actual).expected_steps
    missing_code = expected[0].step_code
    with_missing = validate_reference_case(reference_for(actual, expected_steps=expected + [ExpectedStep(step_code="TEST_EXPECTED_MISSING", step_name="TEST expected missing")]), actual)
    assert any(item.identity == "TEST_EXPECTED_MISSING" and item.status == MatchStatus.MISSING for item in with_missing.items)
    with_extra = validate_reference_case(reference_for(actual, expected_steps=expected[1:]), actual)
    assert any(item.identity == missing_code and item.status == MatchStatus.EXTRA for item in with_extra.items)


def test_assessment_status_and_required_action_mismatch():
    actual = result()
    first = next(item for item in actual.assessments if item.assessment_code)
    expected = [ExpectedAssessment(assessment_code=first.assessment_code, status="TEST_DIFFERENT", required_action="TEST_DIFFERENT")]
    report = validate_reference_case(reference_for(actual, expected_assessments=expected), actual)
    mismatch = next(item for item in report.items if item.category == "assessment" and item.identity == first.assessment_code)
    assert mismatch.status == MatchStatus.DIFFERENT
    assert set(mismatch.detail.split(", ")) == {"status", "required_action"}


def test_missing_canonical_legal_reference_is_reported():
    actual = result()
    expected = [ExpectedLegalReference(step_code=actual.procedures[0].step_code, law_key="TEST_LAW_KEY_DO_NOT_USE")]
    report = validate_reference_case(reference_for(actual, expected_legal_references=expected), actual)
    assert statuses(report, "legal_reference") == [MatchStatus.MISSING]


def test_document_and_agency_missing_extra_and_normalized_match():
    actual = result()
    step = actual.procedures[0]
    expected = ExpectedStep(
        step_code=step.step_code,
        step_name=step.step_name,
        required_documents=[f"  {step.required_documents[0].upper()}  ", "TEST missing document"],
        related_agencies=[f"  {step.related_agencies[0].upper()}  ", "TEST missing agency"],
        estimated_duration=None,
    )
    report = validate_reference_case(reference_for(actual, expected_steps=[expected]), actual)
    assert MatchStatus.MATCH in statuses(report, "document")
    assert MatchStatus.MISSING in statuses(report, "document")
    assert MatchStatus.EXTRA in statuses(report, "document")
    assert MatchStatus.MATCH in statuses(report, "agency")
    assert MatchStatus.MISSING in statuses(report, "agency")
    assert MatchStatus.UNVERIFIED in statuses(report, "duration")


def test_unverified_is_not_failure_and_zero_denominator_is_unavailable():
    actual = result()
    report = validate_reference_case(reference_for(actual, expected_steps=None, expected_assessments=None, expected_legal_references=None), actual)
    assert report.procedure_match_rate.status == "UNAVAILABLE"
    assert report.procedure_match_rate.rate_percent is None
    assert report.unverified_items
    assert not [item for item in report.mismatches if item.status == MatchStatus.UNVERIFIED]
    empty = validate_reference_case(reference_for(actual, expected_steps=[]), actual)
    assert empty.procedure_match_rate.verified_expected == 0
    assert empty.procedure_match_rate.rate_percent is None


def test_fixture_loader_blocks_test_data_from_verified_production_path():
    with pytest.raises(ValueError, match="not allowed"):
        load_reference_case(FIXTURE)
    loaded = load_reference_case(FIXTURE, allow_test_fixture=True)
    assert loaded.data_classification == "TEST_SAMPLE_FIXTURE"
    assert all(marker in loaded.fixture_id for marker in ("TEST", "SAMPLE", "FIXTURE"))


def test_report_identity_warning_and_existing_analyze_schema_unchanged():
    actual = result().model_copy(update={"analysis_id": 57, "project_id": 570})
    report = validate_reference_case(reference_for(actual), actual)
    assert report.analysis_id == 57 and report.project_id == 570
    assert report.data_classification == "TEST_SAMPLE_FIXTURE"
    assert any("not evidence about a real project" in warning for warning in report.warnings)
    fields = set(AnalyzeResponse.model_fields)
    assert "reference_validation" not in fields
    assert "validation_report" not in fields
