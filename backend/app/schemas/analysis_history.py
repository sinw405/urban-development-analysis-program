from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


AnalysisSort = Literal["created_at_desc", "created_at_asc"]


class AnalysisSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    analysis_id: int
    project_id: int
    project_name: str
    location: str
    area_square_meters: float
    local_government: str
    created_at: datetime


class AnalysisListResponse(BaseModel):
    items: list[AnalysisSummary]
    total: int
    limit: int
    offset: int


class AnalysisDetail(BaseModel):
    analysis_id: int
    project_id: int
    project_name: str
    request_payload: dict[str, Any]
    result_payload: dict[str, Any]
    rule_version: str | None
    created_at: datetime
