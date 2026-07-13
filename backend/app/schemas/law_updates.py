from datetime import date, datetime
from typing import Any

from pydantic import BaseModel


class LawUpdateEventSummary(BaseModel):
    event_id: int
    event_kind: str = "legacy_law_update"
    law_id: int | str | None
    law_name: str | None = None
    article_id: int | None = None
    previous_version_id: int | None = None
    new_version_id: int | None = None
    from_mst: str | None = None
    to_mst: str | None = None
    from_effective_date: date | None = None
    to_effective_date: date | None = None
    article_no: str | None = None
    article_title: str | None = None
    change_type: str
    detected_at: datetime
    effective_date: date | None = None
    impacted_step_codes: list[str]
    affected_procedure_code: str | None = None
    affected_procedure_name: str | None = None
    impact_level: str | None = None
    review_status: str | None = None
    mapping_status: str | None = None
    impact_reason: str | None = None
    official_url: str | None = None
    official_url_status: str = "unavailable"
    applicable: bool | None = None
    status: str
    source: str
    metadata_json: dict[str, Any] | None = None


class LawUpdateEventListResponse(BaseModel):
    items: list[LawUpdateEventSummary]
    since: date | None = None
