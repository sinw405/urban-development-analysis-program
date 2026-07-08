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


class ProcedureStep(BaseModel):
    step_code: str
    step_name: str
    sequence: int
    description: str
    required_documents: list[str]
    related_agencies: list[str]
    estimated_duration: str
    legal_basis_placeholder: list[str]
    legal_references: list[LegalReference] = Field(default_factory=list)
    legal_reference_status: str = "missing"
    notes: list[str] = Field(default_factory=list)


class AssessmentItem(BaseModel):
    name: str
    status: str
    threshold: str
    legal_basis: str
    required_action: str
    notes: list[str] = Field(default_factory=list)
    assessment_code: str | None = None


class AnalyzeResponse(BaseModel):
    project_name: str
    location: str
    area_square_meters: float
    implementation_method: str
    implementer_type: str
    local_government: str
    as_of: date | None = None
    procedures: list[ProcedureStep]
    assessments: list[AssessmentItem]
    warnings: list[str]
    project_id: int | None = None
    analysis_id: int | None = None
    created_at: datetime | None = None
