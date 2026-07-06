from app.schemas.analyze import (
    AnalyzeRequest,
    AnalyzeResponse,
    AssessmentItem,
    ProcedureStep,
)
from app.services.rule_loader import load_yaml_rule


LEGAL_WARNING = (
    "Phase 0 MVP result. Legal article numbers and assessment thresholds are placeholders "
    "until MOLEG Open API integration and expert review are completed."
)


def analyze_project(request: AnalyzeRequest) -> AnalyzeResponse:
    procedure_rules = load_yaml_rule("procedure_rules.yaml")
    assessment_rules = load_yaml_rule("assessment_rules.yaml")

    procedures = [
        ProcedureStep(
            order=step["order"],
            name=step["name"],
            description=step.get("description", ""),
            legal_basis=step.get("legal_basis", []),
            required_documents=step.get("required_documents", []),
            consultation_agencies=step.get("consultation_agencies", []),
            estimated_duration=step.get("estimated_duration", "TODO_EXPERT_REVIEW"),
            notes=step.get("notes", []),
        )
        for step in procedure_rules.get("procedure_steps", [])
    ]

    assessments = [
        AssessmentItem(
            name=item["name"],
            status=item.get("status", "TODO_LEGAL_REVIEW_REQUIRED"),
            threshold=item.get("threshold", "TODO_LEGAL_REVIEW_REQUIRED"),
            legal_basis=item.get("legal_basis", "TODO_MOLEG_API"),
            required_action=item.get("required_action", "TODO_EXPERT_REVIEW"),
            notes=item.get("notes", []),
        )
        for item in assessment_rules.get("assessment_items", [])
    ]

    return AnalyzeResponse(
        project_name=request.project_name,
        location=request.location,
        area_square_meters=request.area_square_meters,
        implementation_method=request.implementation_method,
        implementer_type=request.implementer_type,
        local_government=request.local_government,
        procedures=procedures,
        assessments=assessments,
        warnings=[
            LEGAL_WARNING,
            "Do not use this MVP output as a final legal determination.",
        ],
    )
