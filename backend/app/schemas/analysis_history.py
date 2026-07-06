from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class AnalysisSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    analysis_id: int
    project_id: int
    project_name: str
    location: str
    area_square_meters: float
    local_government: str
    created_at: datetime


class AnalysisDetail(BaseModel):
    analysis_id: int
    project_id: int
    project_name: str
    request_payload: dict[str, Any]
    result_payload: dict[str, Any]
    rule_version: str | None
    created_at: datetime
