from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field


class AnalyzeRequest(BaseModel):
    project_name: str = Field(..., description="Name of the urban development project")
    location: str = Field(..., description="Project location")
    area_square_meters: float = Field(..., gt=0, description="Project area in square meters")
    implementation_method: str = Field(..., description="Implementation method")
    implementer_type: str = Field(..., description="Type of project implementer")
    local_government: str = Field(..., description="Relevant local government")
    as_of: date | None = Field(default=None, description="Optional date for stored legal reference version lookup")
    assessment_inputs: dict[str, Any] = Field(
        default_factory=dict,
        description="Optional assessment-specific facts; values are never treated as legal thresholds by themselves",
    )


class LegalReferenceVersion(BaseModel):
    version_id: int
    version_status: str
    temporal_status: str
    effective_date: date | None = None
    source: str


class LegalReference(BaseModel):
    step_code: str
    reference_status: str
    reference_quality: str = "candidate"
    placeholder: str
    law_id: int | None = None
    law_key: str | None = None
    law_mapping_status: str | None = None
    article_id: int | None = None
    article_key: str | None = None
    article_mapping_status: str | None = None
    current_version: LegalReferenceVersion | None = None
    versions: list[LegalReferenceVersion] = Field(default_factory=list)
    notes: dict[str, Any] = Field(default_factory=dict)


class ProcedureArticleCandidate(BaseModel):
    id: int | None = None
    procedure_code: str
    procedure_name: str | None = None
    article_id: int | None = None
    document_id: int | None = None
    law_title: str
    law_short_title: str | None = None
    law_id: str | None = None
    mst: str | None = None
    article_no: str | None = None
    article_title: str | None = None
    article_anchor: str | None = None
    match_method: str
    match_score: float
    match_status: str
    confidence_level: str
    source_mode: str
    source_mode_detail: str | None = None
    is_confirmed: bool = False
    generated_at: datetime | None = None
    confirmed_at: datetime | None = None
    confirmed_by: str | None = None
    confirmed_source: str | None = None
    confirmation_note: str | None = None


class ProcedureStep(BaseModel):
    step_code: str
    step_name: str
    sequence: int
    standard_stage_code: str | None = None
    standard_stage_name: str | None = None
    depends_on: list[str] = Field(default_factory=list)
    description: str
    required_documents: list[str]
    related_agencies: list[str]
    estimated_duration: str
    legal_basis_placeholder: list[str]
    legal_references: list[LegalReference] = Field(default_factory=list)
    legal_reference_status: str = "missing"
    official_article_candidates: list[ProcedureArticleCandidate] = Field(default_factory=list)
    legal_reference_candidates: list[ProcedureArticleCandidate] = Field(default_factory=list)
    reference_candidate_count: int = 0
    reference_status: str = "needs_seed_data"
    notes: list[str] = Field(default_factory=list)


class StandardProcedureStage(BaseModel):
    stage_code: str
    stage_name: str
    sequence: int
    depends_on: list[str] = Field(default_factory=list)
    detail_step_codes: list[str] = Field(default_factory=list)
    legal_basis_status: str = "unresolved"


class AssessmentApplicabilityEvidence(BaseModel):
    evidence_status: str
    hierarchy: str
    law_name: str
    mst: str
    effective_date: date | None = None
    article_number: str | None = None
    article_title: str | None = None
    attached_table_number: str | None = None
    attached_table_title: str | None = None
    source: str
    supports: str
    notes: list[str] = Field(default_factory=list)


class AssessmentItem(BaseModel):
    name: str
    status: str
    threshold: str
    legal_basis: str
    required_action: str
    notes: list[str] = Field(default_factory=list)
    assessment_code: str | None = None
    determination_status: str = "UNRESOLVED"
    determination_reason: str = "Assessment criteria are not verified."
    condition: str = "unresolved"
    required_inputs: list[str] = Field(default_factory=list)
    missing_inputs: list[str] = Field(default_factory=list)
    legal_basis_status: str = "placeholder"
    applicability_status: str = "unresolved"
    threshold_status: str = "placeholder"
    verified_outcome: str | None = None
    requires_expert_review: bool = True
    applicability_evidence: list[AssessmentApplicabilityEvidence] = Field(default_factory=list)
    legal_references: list[LegalReference] = Field(default_factory=list)
    as_of: date | None = None


class AnalyzeResponse(BaseModel):
    project_name: str
    location: str
    area_square_meters: float
    implementation_method: str
    implementer_type: str
    local_government: str
    as_of: date | None = None
    procedures: list[ProcedureStep]
    standard_procedure_graph: list[StandardProcedureStage] = Field(default_factory=list)
    assessments: list[AssessmentItem]
    warnings: list[str]
    project_id: int | None = None
    analysis_id: int | None = None
    created_at: datetime | None = None
