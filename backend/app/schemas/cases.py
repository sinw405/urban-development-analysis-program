from __future__ import annotations

from datetime import date as Date, datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class CaseDataClassification(str, Enum):
    DRAFT = 'DRAFT'
    UNVERIFIED = 'UNVERIFIED'
    VERIFIED_REFERENCE = 'VERIFIED_REFERENCE'
    TEST_SAMPLE_FIXTURE = 'TEST_SAMPLE_FIXTURE'


class CaseVerificationStatus(str, Enum):
    UNVERIFIED = 'UNVERIFIED'
    VERIFIED = 'VERIFIED'


class CaseHistoryItem(BaseModel):
    stage: str | None = None
    date: Date | None = None
    status: str | None = None
    description: str | None = None


class CaseHistoryInput(BaseModel):
    model_config = ConfigDict(extra='forbid')

    stage: str = Field(..., min_length=1)
    date: Date | None = None
    status: str | None = Field(default=None, min_length=1)
    description: str | None = Field(default=None, min_length=1)


class CaseProvenance(BaseModel):
    model_config = ConfigDict(extra='forbid')

    source_title: str | None = Field(default=None, min_length=1)
    source_type: str | None = Field(default=None, min_length=1)
    source_reference: str | None = Field(default=None, min_length=1)
    verified_at: datetime | None = None
    verification_status: CaseVerificationStatus = CaseVerificationStatus.UNVERIFIED
    notes: str | None = Field(default=None, min_length=1)


class CaseBase(BaseModel):
    model_config = ConfigDict(extra='forbid')

    name: str = Field(..., min_length=1, max_length=255)
    location: str | None = Field(default=None, min_length=1, max_length=500)
    area_m2: float | None = Field(default=None, gt=0)
    method: str | None = Field(default=None, min_length=1, max_length=255)
    operator_type: str | None = Field(default=None, min_length=1, max_length=255)
    timeline: list[CaseHistoryInput] = Field(default_factory=list)
    history: list[CaseHistoryInput] = Field(default_factory=list)
    data_classification: CaseDataClassification = CaseDataClassification.DRAFT
    provenance: CaseProvenance = Field(default_factory=CaseProvenance)

    @field_validator('name', 'location', 'method', 'operator_type', mode='before')
    @classmethod
    def reject_blank_strings(cls, value):
        if isinstance(value, str) and not value.strip():
            raise ValueError('Blank strings are not allowed')
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode='after')
    def protect_test_classification(self):
        if self.data_classification == CaseDataClassification.TEST_SAMPLE_FIXTURE:
            raise ValueError('TEST_SAMPLE_FIXTURE cannot be stored through the production cases API')
        if self.data_classification == CaseDataClassification.VERIFIED_REFERENCE:
            project_values = (self.location, self.area_m2, self.method, self.operator_type)
            source_values = (
                self.provenance.source_title,
                self.provenance.source_type,
                self.provenance.source_reference,
                self.provenance.verified_at,
            )
            if not all(project_values):
                raise ValueError('VERIFIED_REFERENCE requires complete project input')
            if self.provenance.verification_status != CaseVerificationStatus.VERIFIED:
                raise ValueError('VERIFIED_REFERENCE requires verified provenance')
            if not all(source_values):
                raise ValueError('VERIFIED_REFERENCE requires complete provenance')
        return self


class CaseCreate(CaseBase):
    pass


class CaseUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid')

    name: str | None = Field(default=None, min_length=1, max_length=255)
    location: str | None = Field(default=None, min_length=1, max_length=500)
    area_m2: float | None = Field(default=None, gt=0)
    method: str | None = Field(default=None, min_length=1, max_length=255)
    operator_type: str | None = Field(default=None, min_length=1, max_length=255)
    timeline: list[CaseHistoryInput] | None = None
    history: list[CaseHistoryInput] | None = None
    data_classification: CaseDataClassification | None = None
    provenance: CaseProvenance | None = None


class CaseComparisonItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    location: str | None = None
    area_m2: float | None = None
    method: str | None = None
    operator_type: str | None = None
    timeline: list[CaseHistoryItem] = Field(default_factory=list)
    history: list[CaseHistoryItem] = Field(default_factory=list)


class CaseDetail(CaseComparisonItem):
    data_classification: CaseDataClassification
    provenance: CaseProvenance
    created_at: datetime
    updated_at: datetime


class CaseComparisonResponse(BaseModel):
    items: list[CaseComparisonItem]
