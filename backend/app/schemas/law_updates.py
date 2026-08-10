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


class LiveLawImpactRequest(BaseModel):
    law_name: str
    from_mst: str | None = None
    to_mst: str | None = None
    dry_run: bool = True
    ensure_versions: bool = True
    persist_event: bool = True
    force_reanalyze: bool = False


class LiveLawVersionSummary(BaseModel):
    mst: str | None = None
    promulgation_date: date | None = None
    effective_date: date | None = None
    status: str | None = None


class LiveLawChangeEventSummary(BaseModel):
    id: int
    idempotency_key: str
    created: bool


class LiveLawImpactResponse(BaseModel):
    law_name: str
    source: str = "MOLEG"
    status: str
    selection_mode: str
    selection_reason: str | None = None
    from_version: LiveLawVersionSummary | None = None
    to_version: LiveLawVersionSummary | None = None
    changed: bool
    version_changed: bool = False
    content_changed: bool | None = None
    analysis_status: str = "missing_version"
    changed_articles: list[dict[str, Any]]
    impacted_rules: list[dict[str, Any]]
    warnings: list[str]
    errors: list[str]
    checked_at: datetime
    discovery: dict[str, Any] | None = None
    event: LiveLawChangeEventSummary | None = None
    version_documents: list[dict[str, Any]] = []
    secret_exposed: bool = False
