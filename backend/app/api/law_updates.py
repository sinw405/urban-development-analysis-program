from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import LawUpdateEvent
from app.schemas.law_updates import LawUpdateEventListResponse, LawUpdateEventSummary
from app.services.law_update_service import get_impacted_step_codes, get_law_update_events

router = APIRouter(tags=["law-updates"])


def _event_summary(db: Session, event: LawUpdateEvent) -> LawUpdateEventSummary:
    return LawUpdateEventSummary(
        event_id=event.id,
        law_id=event.law_id,
        article_id=event.article_id,
        previous_version_id=event.previous_version_id,
        new_version_id=event.new_version_id,
        change_type=event.change_type,
        detected_at=event.detected_at,
        effective_date=event.effective_date,
        impacted_step_codes=get_impacted_step_codes(db=db, article_id=event.article_id),
        status=event.status,
        source=event.source,
        metadata_json=event.metadata_json,
    )


@router.get("/law-updates", response_model=LawUpdateEventListResponse)
def list_law_update_events(
    since: date | None = Query(default=None),
    db: Session = Depends(get_db),
) -> LawUpdateEventListResponse:
    events = get_law_update_events(db=db, since=since)
    return LawUpdateEventListResponse(
        since=since,
        items=[_event_summary(db=db, event=event) for event in events],
    )


@router.get("/law-updates/{event_id}", response_model=LawUpdateEventSummary)
def get_law_update_event(event_id: int, db: Session = Depends(get_db)) -> LawUpdateEventSummary:
    event = db.get(LawUpdateEvent, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Law update event not found")
    return _event_summary(db=db, event=event)
