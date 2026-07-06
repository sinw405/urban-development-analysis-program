from datetime import datetime

from pydantic import BaseModel, Field


class AnalyzeRequest(BaseModel):
    project_name: str = Field(..., description="Name of the urban development project")
    location: str = Field(..., description="Project location")
    area_square_meters: float = Field(..., gt=0, description="Project area in square meters")
    implementation_method: str = Field(..., description="Implementation method")
    implementer_type: str = Field(..., description="Type of project implementer")
    local_government: str = Field(..., description="Relevant local government")


class ProcedureStep(BaseModel):
    order: int
    name: str
    description: str
    legal_basis: list[str]
    required_documents: list[str]
    consultation_agencies: list[str]
    estimated_duration: str
    notes: list[str] = []


class AssessmentItem(BaseModel):
    name: str
    status: str
    threshold: str
    legal_basis: str
    required_action: str
    notes: list[str] = []


class AnalyzeResponse(BaseModel):
    project_name: str
    location: str
    area_square_meters: float
    implementation_method: str
    implementer_type: str
    local_government: str
    procedures: list[ProcedureStep]
    assessments: list[AssessmentItem]
    warnings: list[str]
    project_id: int | None = None
    analysis_id: int | None = None
    created_at: datetime | None = None
