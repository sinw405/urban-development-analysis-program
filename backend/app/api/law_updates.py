from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import LawChangeImpactEvent, LawUpdateEvent
from app.schemas.law_updates import (
    LawUpdateEventListResponse,
    LawUpdateEventSummary,
    LiveLawImpactRequest,
    LiveLawImpactResponse,
    LiveLawVersionSummary,
)
from app.services.law_update_service import get_impacted_step_codes, get_law_update_events
from app.services.law_version_impact_service import list_law_change_impact_events
from app.services.moleg_live_client import MolegLiveClient
from app.services.moleg_version_discovery_service import analyze_live_law_change

router = APIRouter(tags=["law-updates"])


def _legacy_event_summary(db: Session, event: LawUpdateEvent) -> LawUpdateEventSummary:
    return LawUpdateEventSummary(
        event_id=event.id,
        event_kind="legacy_law_update",
        law_id=event.law_id,
        article_id=event.article_id,
        previous_version_id=event.previous_version_id,
        new_version_id=event.new_version_id,
        change_type=event.change_type,
        detected_at=event.detected_at,
        effective_date=event.effective_date,
        impacted_step_codes=get_impacted_step_codes(db=db, article_id=event.article_id),
        applicable=True,
        status=event.status,
        source=event.source,
        metadata_json=event.metadata_json,
    )


def _impact_event_summary(event: LawChangeImpactEvent) -> LawUpdateEventSummary:
    impacted = [] if event.affected_procedure_code is None else [event.affected_procedure_code]
    return LawUpdateEventSummary(
        event_id=event.id,
        event_kind="law_change_impact",
        law_id=event.law_id,
        law_name=event.law_name,
        from_mst=event.from_mst,
        to_mst=event.to_mst,
        from_effective_date=event.from_effective_date,
        to_effective_date=event.to_effective_date,
        article_no=event.article_no,
        article_title=event.article_title,
        change_type=event.change_type,
        detected_at=event.detected_at,
        effective_date=event.to_effective_date,
        impacted_step_codes=impacted,
        affected_procedure_code=event.affected_procedure_code,
        affected_procedure_name=event.affected_procedure_name,
        impact_level=event.impact_level,
        review_status=event.derived_review_status,
        mapping_status=event.mapping_status,
        impact_reason=event.impact_reason,
        official_url=event.official_url,
        official_url_status=event.official_url_status,
        applicable=event.derived_review_status not in {"needs_revalidation", "stale"},
        status=event.status,
        source="MOLEG_CHANGE_IMPACT",
        metadata_json=event.metadata_json,
    )


def _all_summaries(db: Session, since: date | None) -> list[LawUpdateEventSummary]:
    legacy = [_legacy_event_summary(db=db, event=event) for event in get_law_update_events(db=db, since=since)]
    impact = [_impact_event_summary(event) for event in list_law_change_impact_events(db=db)]
    if since is not None:
        impact = [item for item in impact if item.detected_at.date() >= since]
    return sorted([*legacy, *impact], key=lambda item: (item.detected_at, item.event_id), reverse=True)


@router.get("/law-updates", response_model=LawUpdateEventListResponse)
def list_law_update_events(
    since: date | None = Query(default=None),
    db: Session = Depends(get_db),
) -> LawUpdateEventListResponse:
    return LawUpdateEventListResponse(since=since, items=_all_summaries(db=db, since=since))


@router.get("/updates", response_model=LawUpdateEventListResponse)
def list_update_events_alias(
    since: date | None = Query(default=None),
    db: Session = Depends(get_db),
) -> LawUpdateEventListResponse:
    return LawUpdateEventListResponse(since=since, items=_all_summaries(db=db, since=since))


@router.post("/law-updates/live-impact", response_model=LiveLawImpactResponse)
def analyze_live_law_update_impact(request: LiveLawImpactRequest, db: Session = Depends(get_db)) -> LiveLawImpactResponse:
    result = analyze_live_law_change(
        db=db,
        client=MolegLiveClient(),
        law_name=request.law_name,
        from_mst=request.from_mst,
        to_mst=request.to_mst,
        dry_run=request.dry_run,
    )
    if result.status in {"invalid_request", "invalid_version_pair"}:
        raise HTTPException(status_code=400, detail={"status": result.status, "errors": result.errors})
    return _live_impact_response(result)


@router.get("/law-updates/{event_id}", response_model=LawUpdateEventSummary)
def get_law_update_event(event_id: int, kind: str | None = Query(default=None), db: Session = Depends(get_db)) -> LawUpdateEventSummary:
    if kind in {None, "law_change_impact"}:
        impact = db.get(LawChangeImpactEvent, event_id)
        if impact is not None:
            return _impact_event_summary(impact)
    if kind in {None, "legacy_law_update"}:
        event = db.get(LawUpdateEvent, event_id)
        if event is not None:
            return _legacy_event_summary(db=db, event=event)
    raise HTTPException(status_code=404, detail="Law update event not found")


def _live_impact_response(result) -> LiveLawImpactResponse:
    selection = result.selection
    impact = result.impact
    changed_articles = []
    impacted_rules: list[str] = []
    changed = False
    if impact is not None:
        changed_articles = [item for item in impact.affected_articles if item.get("change_type") != "unchanged"]
        impacted_rules = sorted({item.get("affected_procedure_code") for item in changed_articles if item.get("affected_procedure_code")})
        summary = impact.diff_summary
        changed = any(summary.get(key, 0) > 0 for key in ("added", "removed", "changed"))
    return LiveLawImpactResponse(
        law_name=result.law_name,
        source=result.source,
        status=result.status,
        selection_mode=result.mode,
        selection_reason=None if selection is None else selection.selection_reason,
        from_version=None if selection is None else _version(selection.from_version),
        to_version=None if selection is None else _version(selection.to_version),
        changed=changed,
        changed_articles=changed_articles,
        impacted_rules=impacted_rules,
        warnings=result.warnings,
        errors=result.errors,
        checked_at=result.checked_at,
        discovery=None if result.discovery is None else {
            "status": result.discovery.status,
            "total_count": result.discovery.total_count,
            "page_count": result.discovery.page_count,
            "requested_pages": result.discovery.requested_pages,
            "collected_item_count": result.discovery.collected_item_count,
            "exact_match_count": result.discovery.exact_match_count,
            "distinct_mst_count": result.discovery.distinct_mst_count,
        },
        secret_exposed=result.secret_exposed,
    )


def _version(version) -> LiveLawVersionSummary:
    return LiveLawVersionSummary(
        mst=version.mst,
        promulgation_date=version.promulgation_date,
        effective_date=version.enforcement_date,
        status=version.status,
    )
