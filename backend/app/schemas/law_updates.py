from datetime import date, datetime
from typing import Any

from pydantic import BaseModel


class LawUpdateEventSummary(BaseModel):
    event_id: int
    law_id: int
    article_id: int
    previous_version_id: int | None
    new_version_id: int | None
    change_type: str
    detected_at: datetime
    effective_date: date | None
    impacted_step_codes: list[str]
    status: str
    source: str
    metadata_json: dict[str, Any] | None = None


class LawUpdateEventListResponse(BaseModel):
    items: list[LawUpdateEventSummary]
    since: date | None = None
