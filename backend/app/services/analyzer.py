from typing import Any

from app.schemas.analyze import (
    AnalyzeRequest,
    AnalyzeResponse,
    AssessmentItem,
    ProcedureStep,
)
from app.services.rule_loader import load_yaml_rule


LEGAL_WARNING = (
    "Phase 2 rule-engine result. Legal article numbers, assessment applicability, "
    "and thresholds are placeholders until MOLEG Open API integration and expert review are completed."
)
DRAFT_WARNING = "Current procedures are draft workflow candidates and not final legal determinations."

IMPLEMENTATION_METHOD_ALIASES = {
    "expropriation_or_use": "expropriation_or_use",
    "expropriation or use": "expropriation_or_use",
    "expropriation or use method": "expropriation_or_use",
    "\uc218\uc6a9 \ub610\ub294 \uc0ac\uc6a9 \ubc29\uc2dd": "expropriation_or_use",
    "\uc218\uc6a9 \ub610\ub294 \uc0ac\uc6a9\ubc29\uc2dd": "expropriation_or_use",
    "\uc218\uc6a9": "expropriation_or_use",
    "replotting": "replotting",
    "replotting method": "replotting",
    "\ud658\uc9c0 \ubc29\uc2dd": "replotting",
    "\ud658\uc9c0\ubc29\uc2dd": "replotting",
    "\ud658\uc9c0": "replotting",
    "mixed": "mixed",
    "mixed method": "mixed",
    "\ud63c\uc6a9 \ubc29\uc2dd": "mixed",
    "\ud63c\uc6a9\ubc29\uc2dd": "mixed",
    "\ud63c\uc6a9": "mixed",
}

IMPLEMENTER_TYPE_ALIASES = {
    "public": "public",
    "public implementer": "public",
    "\uacf5\uacf5": "public",
    "private": "private",
    "private implementer": "private",
    "\ubbfc\uac04": "private",
    "public_private_spc": "public_private_spc",
    "public-private spc": "public_private_spc",
    "public private spc": "public_private_spc",
    "\ubbfc\uad00spc": "public_private_spc",
    "\ubbfc\uad00SPC": "public_private_spc",
    "\ubbfc\uad00\ud611\ub3d9 spc": "public_private_spc",
    "\ubbfc\uad00\ud611\ub3d9 SPC": "public_private_spc",
    "\ubbfc\uad00\ud611\ub3d9SPC": "public_private_spc",
}


def _normalize(value: str, aliases: dict[str, str]) -> str | None:
    raw = value.strip()
    if raw in aliases:
        return aliases[raw]
    lowered = raw.lower()
    return aliases.get(lowered)


def _step_from_rule(step: dict[str, Any]) -> ProcedureStep:
    return ProcedureStep(
        step_code=step["step_code"],
        step_name=step["step_name"],
        sequence=step["sequence"],
        description=step.get("description", ""),
        required_documents=step.get("required_documents", []),
        related_agencies=step.get("related_agencies", []),
        estimated_duration=step.get("estimated_duration", "TODO_EXPERT_REVIEW"),
        legal_basis_placeholder=step.get("legal_basis_placeholder", ["TODO_MOLEG_API_ARTICLE_CHECK"]),
        legal_references=[],
        notes=step.get("notes", []),
    )


def _build_procedures(
    procedure_rules: dict[str, Any],
    implementation_method: str,
    implementer_type: str,
    warnings: list[str],
) -> list[ProcedureStep]:
    normalized_method = _normalize(implementation_method, IMPLEMENTATION_METHOD_ALIASES)
    normalized_implementer = _normalize(implementer_type, IMPLEMENTER_TYPE_ALIASES)

    if normalized_method is None:
        warnings.append(
            f"Unknown implementation_method '{implementation_method}'. Only common procedure candidates were applied."
        )
    if normalized_implementer is None:
        warnings.append(
            f"Unknown implementer_type '{implementer_type}'. Only common implementer-neutral candidates were applied."
        )

    raw_steps: list[dict[str, Any]] = list(procedure_rules.get("common_steps", []))

    method_rules = procedure_rules.get("implementation_method_rules", {})
    if normalized_method:
        raw_steps.extend(method_rules.get(normalized_method, {}).get("add_steps", []))

    implementer_rules = procedure_rules.get("implementer_type_rules", {})
    if normalized_implementer:
        raw_steps.extend(implementer_rules.get(normalized_implementer, {}).get("add_steps", []))

    steps_by_code: dict[str, ProcedureStep] = {}
    for raw_step in raw_steps:
        step = _step_from_rule(raw_step)
        steps_by_code.setdefault(step.step_code, step)

    return sorted(steps_by_code.values(), key=lambda item: (item.sequence, item.step_code))


def _build_assessments(assessment_rules: dict[str, Any]) -> list[AssessmentItem]:
    assessments: list[AssessmentItem] = []
    for item in assessment_rules.get("assessment_items", []):
        assessments.append(
            AssessmentItem(
                assessment_code=item.get("assessment_code"),
                name=item["name"],
                status=item.get("status", "\ubc95\ub839 \uac80\ud1a0 \ud544\uc694"),
                threshold=item.get("threshold", "TODO_PLACEHOLDER_DO_NOT_USE_AS_CRITERIA"),
                legal_basis=item.get("legal_basis", "TODO_MOLEG_API_ARTICLE_CHECK"),
                required_action=item.get(
                    "required_action",
                    "\uae30\uc900 \ubbf8\ud655\uc815: \ucd94\ud6c4 \ubc95\uc81c\ucc98 Open API \ubc0f \uc804\ubb38\uac00 \uac80\ud1a0 \ud6c4 \ud655\uc815 \ud544\uc694",
                ),
                notes=item.get("notes", []),
            )
        )
    return assessments


def analyze_project(request: AnalyzeRequest) -> AnalyzeResponse:
    procedure_rules = load_yaml_rule("procedure_rules.yaml")
    assessment_rules = load_yaml_rule("assessment_rules.yaml")

    warnings = [
        LEGAL_WARNING,
        DRAFT_WARNING,
        "Actual legal criteria must be finalized later through MOLEG Open API and expert review.",
    ]

    procedures = _build_procedures(
        procedure_rules=procedure_rules,
        implementation_method=request.implementation_method,
        implementer_type=request.implementer_type,
        warnings=warnings,
    )
    assessments = _build_assessments(assessment_rules)

    return AnalyzeResponse(
        project_name=request.project_name,
        location=request.location,
        area_square_meters=request.area_square_meters,
        implementation_method=request.implementation_method,
        implementer_type=request.implementer_type,
        local_government=request.local_government,
        procedures=procedures,
        assessments=assessments,
        warnings=warnings,
    )
