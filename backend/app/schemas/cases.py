from __future__ import annotations

from datetime import date as Date

from pydantic import BaseModel, ConfigDict, Field


class CaseHistoryItem(BaseModel):
    stage: str | None = None
    date: Date | None = None
    status: str | None = None
    description: str | None = None


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


class CaseComparisonResponse(BaseModel):
    items: list[CaseComparisonItem]
