from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from app.schemas.analyze import AnalyzeResponse, ProcedureStep
from app.schemas.reference_validation import (
    MatchRate,
    MatchStatus,
    ReferenceCaseValidationInput,
    ReferenceCaseValidationReport,
    ValidationItem,
)


def load_reference_case(path: str | Path, *, allow_test_fixture: bool = False) -> ReferenceCaseValidationInput:
    case = ReferenceCaseValidationInput.model_validate_json(Path(path).read_text(encoding="utf-8"))
    if case.data_classification == "TEST_SAMPLE_FIXTURE" and not allow_test_fixture:
        raise ValueError("TEST/SAMPLE/FIXTURE data is not allowed as a verified production reference")
    return case


def _normalize(value: str) -> str:
    return " ".join(value.split()).casefold()


def _set_items(category: str, identity: str, expected: list[str] | None, actual: list[str]) -> list[ValidationItem]:
    if expected is None:
        return [ValidationItem(category=category, identity=identity, status=MatchStatus.UNVERIFIED, detail="Reference data unavailable")]
    expected_map = {_normalize(value): value for value in expected}
    actual_map = {_normalize(value): value for value in actual}
    items = [
        ValidationItem(category=category, identity=f"{identity}:{key}", status=MatchStatus.MATCH if key in actual_map else MatchStatus.MISSING, expected=value, actual=actual_map.get(key))
        for key, value in expected_map.items()
    ]
    items.extend(
        ValidationItem(category=category, identity=f"{identity}:{key}", status=MatchStatus.EXTRA, actual=value)
        for key, value in actual_map.items() if key not in expected_map
    )
    return items


def _procedure_items(reference: ReferenceCaseValidationInput, result: AnalyzeResponse) -> tuple[list[ValidationItem], MatchRate]:
    if reference.expected_steps is None:
        item = ValidationItem(category="procedure", identity="procedures", status=MatchStatus.UNVERIFIED, detail="Verified expected steps unavailable")
        return [item], MatchRate(matched=0, verified_expected=0, rate_percent=None, status="UNAVAILABLE")
    actual = {step.step_code: step for step in result.procedures}
    expected = {step.step_code: step for step in reference.expected_steps}
    items: list[ValidationItem] = []
    matched = 0
    for code, expected_step in expected.items():
        actual_step = actual.get(code)
        if actual_step is None:
            status = MatchStatus.MISSING
        elif expected_step.step_name is not None and _normalize(expected_step.step_name) != _normalize(actual_step.step_name):
            status = MatchStatus.DIFFERENT
        else:
            status = MatchStatus.MATCH
            matched += 1
        items.append(ValidationItem(category="procedure", identity=code, status=status, expected=expected_step.step_name, actual=actual_step.step_name if actual_step else None))
    items.extend(ValidationItem(category="procedure", identity=code, status=MatchStatus.EXTRA, actual=step.step_name) for code, step in actual.items() if code not in expected)
    denominator = len(expected)
    rate = round(matched / denominator * 100, 2) if denominator else None
    return items, MatchRate(matched=matched, verified_expected=denominator, rate_percent=rate, status="AVAILABLE" if denominator else "UNAVAILABLE")


def _assessment_items(reference: ReferenceCaseValidationInput, result: AnalyzeResponse) -> list[ValidationItem]:
    if reference.expected_assessments is None:
        return [ValidationItem(category="assessment", identity="assessments", status=MatchStatus.UNVERIFIED, detail="Reference data unavailable")]
    actual = {item.assessment_code: item for item in result.assessments if item.assessment_code}
    expected = {item.assessment_code: item for item in reference.expected_assessments}
    items: list[ValidationItem] = []
    for code, expected_item in expected.items():
        actual_item = actual.get(code)
        if actual_item is None:
            status, detail = MatchStatus.MISSING, None
        else:
            differences = []
            if expected_item.status is not None and _normalize(expected_item.status) != _normalize(actual_item.status): differences.append("status")
            if expected_item.required_action is not None and _normalize(expected_item.required_action) != _normalize(actual_item.required_action): differences.append("required_action")
            status, detail = (MatchStatus.DIFFERENT, ", ".join(differences)) if differences else (MatchStatus.MATCH, None)
        items.append(ValidationItem(category="assessment", identity=code, status=status, expected=expected_item.status, actual=actual_item.status if actual_item else None, detail=detail))
    items.extend(ValidationItem(category="assessment", identity=code, status=MatchStatus.EXTRA, actual=item.status) for code, item in actual.items() if code not in expected)
    return items


def _legal_reference_identity(step_code: str, law_key: str | None, article_key: str | None) -> str:
    return f"{step_code}|{law_key or ''}|{article_key or ''}"


def _legal_items(reference: ReferenceCaseValidationInput, result: AnalyzeResponse) -> list[ValidationItem]:
    if reference.expected_legal_references is None:
        return [ValidationItem(category="legal_reference", identity="legal_references", status=MatchStatus.UNVERIFIED, detail="Verified legal reference data unavailable")]
    expected = {_legal_reference_identity(item.step_code, item.law_key, item.article_key) for item in reference.expected_legal_references}
    actual = {
        _legal_reference_identity(step.step_code, item.law_key, item.article_key)
        for step in result.procedures for item in step.legal_references if item.law_key or item.article_key
    }
    return [ValidationItem(category="legal_reference", identity=value, status=MatchStatus.MATCH if value in actual else MatchStatus.MISSING, expected=value, actual=value if value in actual else None) for value in sorted(expected)] + [ValidationItem(category="legal_reference", identity=value, status=MatchStatus.EXTRA, actual=value) for value in sorted(actual - expected)]


def _step_detail_items(reference: ReferenceCaseValidationInput, result: AnalyzeResponse) -> list[ValidationItem]:
    if reference.expected_steps is None:
        return [ValidationItem(category=category, identity=category, status=MatchStatus.UNVERIFIED, detail="Reference steps unavailable") for category in ("document", "agency", "duration")]
    actual: dict[str, ProcedureStep] = {step.step_code: step for step in result.procedures}
    items: list[ValidationItem] = []
    for expected in reference.expected_steps:
        step = actual.get(expected.step_code)
        items.extend(_set_items("document", expected.step_code, expected.required_documents, step.required_documents if step else []))
        items.extend(_set_items("agency", expected.step_code, expected.related_agencies, step.related_agencies if step else []))
        if expected.estimated_duration is None:
            items.append(ValidationItem(category="duration", identity=expected.step_code, status=MatchStatus.UNVERIFIED, actual=step.estimated_duration if step else None, detail="Verified duration unavailable"))
        elif step is None:
            items.append(ValidationItem(category="duration", identity=expected.step_code, status=MatchStatus.MISSING, expected=expected.estimated_duration))
        else:
            status = MatchStatus.MATCH if _normalize(expected.estimated_duration) == _normalize(step.estimated_duration) else MatchStatus.DIFFERENT
            items.append(ValidationItem(category="duration", identity=expected.step_code, status=status, expected=expected.estimated_duration, actual=step.estimated_duration))
    return items


def validate_reference_case(reference: ReferenceCaseValidationInput, result: AnalyzeResponse) -> ReferenceCaseValidationReport:
    procedures, rate = _procedure_items(reference, result)
    items = procedures + _assessment_items(reference, result) + _legal_items(reference, result) + _step_detail_items(reference, result)
    mismatches = [item for item in items if item.status in {MatchStatus.MISSING, MatchStatus.EXTRA, MatchStatus.DIFFERENT}]
    unverified = [item for item in items if item.status == MatchStatus.UNVERIFIED]
    warnings = []
    if reference.data_classification == "TEST_SAMPLE_FIXTURE": warnings.append("TEST/SAMPLE/FIXTURE report; not evidence about a real project")
    if rate.status == "UNAVAILABLE": warnings.append("Procedure match rate unavailable because no verified expected steps exist")
    return ReferenceCaseValidationReport(
        fixture_id=reference.fixture_id, reference_case_name=reference.reference_case_name,
        data_classification=reference.data_classification, analysis_id=result.analysis_id, project_id=result.project_id,
        as_of=result.as_of, validated_at=datetime.now(timezone.utc), procedure_match_rate=rate,
        items=items, mismatches=mismatches, unverified_items=unverified, warnings=warnings,
    )
