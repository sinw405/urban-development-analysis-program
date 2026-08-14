from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.schemas.analyze import AnalyzeRequest


class MatchStatus(str, Enum):
    MATCH = "MATCH"
    MISSING = "MISSING"
    EXTRA = "EXTRA"
    DIFFERENT = "DIFFERENT"
    UNVERIFIED = "UNVERIFIED"


class ExpectedStep(BaseModel):
    step_code: str = Field(..., min_length=1)
    step_name: str | None = None
    required_documents: list[str] | None = None
    related_agencies: list[str] | None = None
    estimated_duration: str | None = None


class ExpectedAssessment(BaseModel):
    assessment_code: str = Field(..., min_length=1)
    status: str | None = None
    required_action: str | None = None


class ExpectedLegalReference(BaseModel):
    step_code: str = Field(..., min_length=1)
    law_key: str | None = None
    article_key: str | None = None

    @model_validator(mode="after")
    def require_identity(self):
        if not self.law_key and not self.article_key:
            raise ValueError("A canonical law_key or article_key is required")
        return self


class ReferenceCaseValidationInput(BaseModel):
    fixture_id: str = Field(..., min_length=1)
    reference_case_name: str = Field(..., min_length=1)
    data_classification: Literal["VERIFIED_REFERENCE", "TEST_SAMPLE_FIXTURE"]
    source_note: str = Field(..., min_length=1)
    project_input: AnalyzeRequest
    expected_steps: list[ExpectedStep] | None = None
    expected_assessments: list[ExpectedAssessment] | None = None
    expected_legal_references: list[ExpectedLegalReference] | None = None


class ValidationItem(BaseModel):
    category: Literal["procedure", "assessment", "legal_reference", "document", "agency", "duration"]
    identity: str
    status: MatchStatus
    expected: str | None = None
    actual: str | None = None
    detail: str | None = None


class MatchRate(BaseModel):
    matched: int
    verified_expected: int
    rate_percent: float | None
    status: Literal["AVAILABLE", "UNAVAILABLE"]
    formula: str = "matched / verified_expected * 100; UNVERIFIED items excluded"


class ReferenceCaseValidationReport(BaseModel):
    fixture_id: str
    reference_case_name: str
    data_classification: Literal["VERIFIED_REFERENCE", "TEST_SAMPLE_FIXTURE"]
    analysis_id: int | None
    project_id: int | None
    as_of: date | None
    validated_at: datetime
    procedure_match_rate: MatchRate
    items: list[ValidationItem]
    mismatches: list[ValidationItem]
    unverified_items: list[ValidationItem]
    warnings: list[str]
