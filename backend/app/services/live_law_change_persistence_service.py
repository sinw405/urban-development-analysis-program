from __future__ import annotations
from dataclasses import dataclass, field
from datetime import UTC, datetime
import hashlib
import logging
from typing import Any
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.models import LiveLawChangeEvent, LiveLawChangeEventAudit, OfficialLawArticleRecord, OfficialLawDocument
from app.services.law_version_impact_service import LawVersionImpactService, LawVersionImpactResult
from app.core.observability import log_event
from app.services.operational_alert_service import emit_operational_alert

logger = logging.getLogger(__name__)

COMPLETE_DOCUMENT_STATUS = "normalized"

@dataclass(frozen=True)
class VersionDocumentState:
    mst: str
    document_id: int | None
    law_name: str | None
    law_id: str | None
    promulgation_date: Any = None
    effective_date: Any = None
    history_status: str | None = None
    article_count: int = 0
    body_present: bool = False
    parsing_complete: bool = False
    @property
    def complete(self) -> bool:
        return self.document_id is not None and self.body_present and self.parsing_complete and self.article_count > 0
    def to_dict(self):
        return self.__dict__.copy() | {"complete": self.complete}

@dataclass
class Phase43ExecutionResult:
    status: str
    analysis_status: str
    version_changed: bool
    content_changed: bool | None = None
    impact: LawVersionImpactResult | None = None
    changed_articles: list[dict[str, Any]] = field(default_factory=list)
    impacted_rules: list[dict[str, Any]] = field(default_factory=list)
    event: LiveLawChangeEvent | None = None
    event_created: bool = False
    version_states: list[VersionDocumentState] = field(default_factory=list)
    ingested_msts: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def get_version_by_mst(db: Session, mst: str, law_name: str | None = None) -> VersionDocumentState:
    statement = select(OfficialLawDocument).where(OfficialLawDocument.mst == str(mst)).order_by(OfficialLawDocument.id.desc())
    documents = list(db.scalars(statement).all())
    if law_name is not None:
        normalized = _normalize(law_name)
        documents = [item for item in documents if _normalize(item.law_title) == normalized]
    if not documents:
        return VersionDocumentState(str(mst), None, law_name, None)
    document = documents[0]
    articles = list(db.scalars(select(OfficialLawArticleRecord).where(OfficialLawArticleRecord.document_id == document.id)).all())
    body_present = bool(articles) and all(bool(_normalize(item.article_text)) for item in articles)
    return VersionDocumentState(str(mst), document.id, document.law_title, document.law_id, document.promulgation_date,
        document.enforcement_date, "current" if document.is_current else "history", len(articles), body_present,
        document.document_status == COMPLETE_DOCUMENT_STATUS and body_present)


def has_version_document(db: Session, mst: str, law_name: str | None = None) -> bool:
    return get_version_by_mst(db, mst, law_name).complete


def build_idempotency_key(source: str, law_identifier: str, from_mst: str, to_mst: str) -> str:
    return hashlib.sha256("|".join([source.casefold(), law_identifier.strip().casefold(), str(from_mst), str(to_mst)]).encode("utf-8")).hexdigest()


def ensure_version_documents(db: Session, client, selection) -> tuple[list[VersionDocumentState], list[str], list[str]]:
    from app.services.moleg_version_discovery_service import ingest_law_versions
    descriptors = [selection.from_version, selection.to_version]
    missing = [item for item in descriptors if not has_version_document(db, item.mst, selection.law_name)]
    if missing:
        ingest = ingest_law_versions(db, client, missing, dry_run=False)
        if ingest.status != "completed":
            return [get_version_by_mst(db, item.mst, selection.law_name) for item in descriptors], [], ingest.errors or [ingest.status]
    states = [get_version_by_mst(db, item.mst, selection.law_name) for item in descriptors]
    incomplete = [item.mst for item in states if not item.complete]
    return states, [item.mst for item in missing], [f"incomplete_version:{mst}" for mst in incomplete]


def execute_phase43(db: Session, client, selection, ensure_versions: bool = True, persist_event: bool = True, force_reanalyze: bool = False) -> Phase43ExecutionResult:
    result = Phase43ExecutionResult("started", "missing_version", selection.from_mst != selection.to_mst)
    law_identifier = selection.to_version.law_id or selection.from_version.law_id or selection.law_name
    key = build_idempotency_key("MOLEG", str(law_identifier), selection.from_mst, selection.to_mst)
    event, created = _get_or_create_event(db, selection, key, persist_event)
    result.event, result.event_created = event, created
    _audit(db, event, "discovered", "discovered", {"selection_reason": selection.selection_reason}, persist_event)
    if ensure_versions:
        _audit(db, event, "ingest_started", "started", {"msts": [selection.from_mst, selection.to_mst]}, persist_event)
        states, ingested, ingest_errors = ensure_version_documents(db, client, selection)
        result.version_states, result.ingested_msts = states, ingested
        if ingest_errors:
            return _fail(db, result, event, "ingest_failed", ingest_errors, persist_event)
        _audit(db, event, "ingest_completed", "completed", {"ingested_msts": ingested, "article_counts": [item.article_count for item in states]}, persist_event)
    else:
        result.version_states = [get_version_by_mst(db, item.mst, selection.law_name) for item in [selection.from_version, selection.to_version]]
    if not all(item.complete for item in result.version_states):
        return _fail(db, result, event, "missing_version", ["version_not_available"], persist_event)
    if event is not None and not created and not force_reanalyze and event.analysis_status in {"completed", "no_change"}:
        result.analysis_status = event.analysis_status
        result.status = "ok"
        result.content_changed = event.content_changed
        result.changed_articles = event.changed_articles_json or []
        result.impacted_rules = event.impacted_rules_json or []
        _audit(db, event, "persisted", "reused", {"idempotency_key": key}, persist_event)
        _monitor_change(result, law_identifier, selection)
        return result
    _audit(db, event, "analysis_started", "started", None, persist_event)
    impact = LawVersionImpactService(db).analyze(selection.law_name, selection.from_mst, selection.to_mst, dry_run=True)
    result.impact = impact
    if impact.status != "ok":
        return _fail(db, result, event, "analysis_failed", impact.errors or [impact.status], persist_event)
    result.changed_articles = [_public_article(item) for item in impact.affected_articles if item.get("change_type") != "unchanged"]
    result.impacted_rules = _impacted_rules(result.changed_articles)
    result.content_changed = bool(result.changed_articles)
    result.analysis_status = "completed" if result.content_changed else "no_change"
    result.status = "ok"
    if not result.content_changed and not result.impacted_rules:
        result.warnings.append("no_content_change")
    elif result.content_changed and not result.impacted_rules:
        result.warnings.append("changed_articles_have_no_rule_mapping")
    if event is not None:
        event.content_changed = result.content_changed
        event.analysis_status = result.analysis_status
        event.changed_article_count = len(result.changed_articles)
        event.impacted_rule_count = len(result.impacted_rules)
        event.changed_articles_json = result.changed_articles
        event.impacted_rules_json = result.impacted_rules
        event.analyzed_at = datetime.now(UTC)
        event.error_code = None
        event.sanitized_error = None
        _audit(db, event, "analysis_completed", result.analysis_status, {"changed_article_count": len(result.changed_articles), "impacted_rule_count": len(result.impacted_rules)}, False)
        _audit(db, event, "persisted", "completed", {"idempotency_key": key}, False)
        if persist_event:
            db.commit()
    _monitor_change(result, law_identifier, selection)
    return result


def _monitor_change(result, law_identifier, selection):
    log_event(logger, logging.INFO, "law.amendment.evaluated", law_identifier=str(law_identifier),
              from_mst=selection.from_mst, to_mst=selection.to_mst,
              version_changed=result.version_changed, content_changed=result.content_changed,
              changed_article_count=len(result.changed_articles), event_id=None if result.event is None else result.event.id,
              event_created=result.event_created)
    if result.content_changed:
        emit_operational_alert("law.amendment.detected", severity="warning",
                               law_identifier=str(law_identifier), from_mst=selection.from_mst,
                               to_mst=selection.to_mst, changed_article_count=len(result.changed_articles))


def _get_or_create_event(db, selection, key, persist):
    existing = db.scalar(select(LiveLawChangeEvent).where(LiveLawChangeEvent.idempotency_key == key))
    if existing is not None:
        return existing, False
    if not persist:
        return None, False
    event = LiveLawChangeEvent(source="MOLEG", law_id=selection.to_version.law_id or selection.from_version.law_id,
        law_name=selection.law_name, from_mst=selection.from_mst, to_mst=selection.to_mst,
        from_effective_date=selection.from_version.enforcement_date, to_effective_date=selection.to_version.enforcement_date,
        version_changed=selection.from_mst != selection.to_mst, content_changed=None, analysis_status="discovered", idempotency_key=key)
    db.add(event)
    try:
        db.commit()
        db.refresh(event)
        return event, True
    except IntegrityError:
        db.rollback()
        return db.scalar(select(LiveLawChangeEvent).where(LiveLawChangeEvent.idempotency_key == key)), False


def _audit(db, event, action, status, detail, commit):
    if event is None:
        return
    db.add(LiveLawChangeEventAudit(event_id=event.id, action=action, status=status, sanitized_detail_json=detail))
    if commit:
        db.commit()


def _fail(db, result, event, status, errors, persist):
    result.status = status
    result.analysis_status = status
    result.errors.extend([_sanitize_error(item) for item in errors])
    if event is not None:
        event.analysis_status = status
        event.error_code = result.errors[0] if result.errors else status
        event.sanitized_error = ";".join(result.errors)[:1000]
        action = "analysis_failed" if status == "analysis_failed" else "ingest_completed"
        _audit(db, event, action, "failed", {"error_code": event.error_code}, False)
        if persist:
            db.commit()
    return result


def _public_article(item):
    result = {key: value for key, value in item.items() if key not in {"duplicate", "source_provenance", "official_url"}}
    if result.get("change_type") == "changed":
        result["change_type"] = "modified"
    return _json_safe(result)


def _impacted_rules(articles):
    result = {}
    for item in articles:
        code = item.get("affected_procedure_code")
        if not code:
            continue
        key = ("procedure", str(code), item.get("article_no"))
        result[key] = {"rule_type": "procedure", "rule_id": str(code), "rule_name": item.get("affected_procedure_name"),
            "related_article": item.get("article_no"), "impact_reason": item.get("impact_reason"),
            "review_required": item.get("derived_review_status") in {"needs_revalidation", "stale", "unconfirmed"}}
    return list(result.values())


def _json_safe(value):
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def _sanitize_error(value):
    text = str(value)
    for marker in ("OC=", "serviceKey=", "MOLEG_API_KEY="):
        if marker in text:
            text = text.split(marker, 1)[0] + marker + "[REDACTED]"
    return text[:1000]

def _normalize(value):
    return " ".join((value or "").strip().casefold().split())
