from typing import Any

from app.schemas.analyze import (
    AnalyzeRequest,
    AnalyzeResponse,
    AssessmentItem,
    ProcedureStep,
    StandardProcedureStage,
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


def _build_standard_graph(
    procedure_rules: dict[str, Any], procedures: list[ProcedureStep]
) -> list[StandardProcedureStage]:
    raw_stages = procedure_rules.get("standard_procedure_graph", [])
    if not isinstance(raw_stages, list) or not raw_stages:
        raise ValueError("standard_procedure_graph must be a non-empty list")

    stage_codes = [stage.get("stage_code") for stage in raw_stages]
    if any(not code for code in stage_codes) or len(stage_codes) != len(set(stage_codes)):
        raise ValueError("standard procedure stage codes must be present and unique")

    detail_to_stage: dict[str, dict[str, Any]] = {}
    seen_stage_codes: set[str] = set()
    for stage in sorted(raw_stages, key=lambda item: (item["sequence"], item["stage_code"])):
        dependencies = set(stage.get("depends_on", []))
        unknown_dependencies = dependencies - set(stage_codes)
        if unknown_dependencies:
            raise ValueError(f"unknown standard stage dependencies: {sorted(unknown_dependencies)}")
        if not dependencies.issubset(seen_stage_codes):
            raise ValueError(f"standard stage dependencies must refer to earlier stages: {stage['stage_code']}")
        seen_stage_codes.add(stage["stage_code"])
        for step_code in stage.get("detail_step_codes", []):
            if step_code in detail_to_stage:
                raise ValueError(f"detail step is mapped to multiple standard stages: {step_code}")
            detail_to_stage[step_code] = stage

    configured_codes = {step["step_code"] for step in procedure_rules.get("common_steps", [])}
    for section in ("implementation_method_rules", "implementer_type_rules"):
        for branch in procedure_rules.get(section, {}).values():
            configured_codes.update(step["step_code"] for step in branch.get("add_steps", []))
    graph_codes = set(detail_to_stage)
    if configured_codes != graph_codes:
        raise ValueError(
            "standard graph detail mappings must match configured procedure steps: "
            f"missing={sorted(configured_codes - graph_codes)}, unknown={sorted(graph_codes - configured_codes)}"
        )

    selected_codes = {step.step_code for step in procedures}
    unmapped = selected_codes - set(detail_to_stage)
    if unmapped:
        raise ValueError(f"procedure steps are missing standard stage mappings: {sorted(unmapped)}")

    selected_by_stage: dict[str, list[ProcedureStep]] = {}
    for step in procedures:
        stage = detail_to_stage[step.step_code]
        step.standard_stage_code = stage["stage_code"]
        step.standard_stage_name = stage["stage_name"]
        selected_by_stage.setdefault(stage["stage_code"], []).append(step)

    graph: list[StandardProcedureStage] = []
    previous_detail_code: str | None = None
    for stage in sorted(raw_stages, key=lambda item: (item["sequence"], item["stage_code"])):
        selected_steps = sorted(
            selected_by_stage.get(stage["stage_code"], []),
            key=lambda item: (item.sequence, item.step_code),
        )
        for step in selected_steps:
            step.depends_on = [] if previous_detail_code is None else [previous_detail_code]
            previous_detail_code = step.step_code
        graph.append(
            StandardProcedureStage(
                stage_code=stage["stage_code"],
                stage_name=stage["stage_name"],
                sequence=stage["sequence"],
                depends_on=stage.get("depends_on", []),
                detail_step_codes=[step.step_code for step in selected_steps],
                legal_basis_status=stage.get("legal_basis_status", "unresolved"),
            )
        )
    return graph


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


def _validate_assessment_rules(assessment_rules: dict[str, Any]) -> None:
    items = assessment_rules.get("assessment_items")
    if not isinstance(items, list) or not items:
        raise ValueError("assessment_items must be a non-empty list")

    codes: list[str] = []
    allowed_basis_statuses = {"verified", "candidate", "unresolved", "placeholder", "missing"}
    allowed_threshold_statuses = {"verified", "unresolved", "placeholder", "not_applicable"}
    for item in items:
        code = item.get("assessment_code")
        if not code:
            raise ValueError("assessment_code is required")
        codes.append(code)
        required_inputs = item.get("required_inputs")
        if not isinstance(required_inputs, list):
            raise ValueError(f"required_inputs must be a list: {code}")
        basis_status = item.get("legal_basis_status", "placeholder")
        if basis_status not in allowed_basis_statuses:
            raise ValueError(f"invalid legal_basis_status for {code}: {basis_status}")
        if basis_status == "verified" and item.get("legal_basis") == "TODO_MOLEG_API_ARTICLE_CHECK":
            raise ValueError(f"placeholder legal basis cannot be marked verified: {code}")
        applicability_status = item.get("applicability_status", "unresolved")
        threshold_status = item.get("threshold_status", "placeholder")
        outcome = item.get("verified_outcome")
        if applicability_status not in allowed_basis_statuses:
            raise ValueError(f"invalid applicability_status for {code}: {applicability_status}")
        if threshold_status not in allowed_threshold_statuses:
            raise ValueError(f"invalid threshold_status for {code}: {threshold_status}")
        if applicability_status == "verified":
            if outcome not in {"REQUIRED", "NOT_REQUIRED", "CONDITIONAL"}:
                raise ValueError(f"verified applicability requires a verified_outcome: {code}")
            if threshold_status not in {"verified", "not_applicable"}:
                raise ValueError(f"verified applicability cannot use an unresolved threshold: {code}")

    if len(codes) != len(set(codes)):
        raise ValueError("assessment codes must be unique")


def _build_assessments(
    assessment_rules: dict[str, Any], request: AnalyzeRequest
) -> list[AssessmentItem]:
    _validate_assessment_rules(assessment_rules)
    assessments: list[AssessmentItem] = []
    for item in assessment_rules["assessment_items"]:
        required_inputs = item.get("required_inputs", [])
        missing_inputs = [key for key in required_inputs if request.assessment_inputs.get(key) is None]
        if missing_inputs:
            determination_status = "NEED_MORE_INFO"
            determination_reason = "Required assessment inputs are missing; applicability was not determined."
        else:
            determination_status = "UNRESOLVED"
            determination_reason = "Applicability criteria are not verified; no required/not-required decision was made."

        assessments.append(
            AssessmentItem(
                assessment_code=item["assessment_code"],
                name=item["name"],
                status=item.get("status", "?? ?? ??"),
                determination_status=determination_status,
                determination_reason=determination_reason,
                condition=item.get("condition", "unresolved"),
                required_inputs=required_inputs,
                missing_inputs=missing_inputs,
                threshold=item.get("threshold", "TODO_PLACEHOLDER_DO_NOT_USE_AS_CRITERIA"),
                legal_basis=item.get("legal_basis", "TODO_MOLEG_API_ARTICLE_CHECK"),
                legal_basis_status=item.get("legal_basis_status", "placeholder"),
                applicability_status=item.get("applicability_status", "unresolved"),
                threshold_status=item.get("threshold_status", "placeholder"),
                verified_outcome=item.get("verified_outcome"),
                requires_expert_review=item.get("requires_expert_review", True),
                legal_references=[],
                as_of=request.as_of,
                required_action=item.get(
                    "required_action",
                    "Provide missing facts and verify stored legal basis before making an applicability decision.",
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
    standard_graph = _build_standard_graph(procedure_rules, procedures)
    assessments = _build_assessments(assessment_rules, request)

    return AnalyzeResponse(
        project_name=request.project_name,
        location=request.location,
        area_square_meters=request.area_square_meters,
        implementation_method=request.implementation_method,
        implementer_type=request.implementer_type,
        local_government=request.local_government,
        as_of=request.as_of,
        procedures=procedures,
        standard_procedure_graph=standard_graph,
        assessments=assessments,
        warnings=warnings,
    )
