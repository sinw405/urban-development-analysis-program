from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any
import hashlib
from urllib.parse import urlparse

from sqlalchemy import func, null, select
from sqlalchemy.orm import Session

from app.models import (
    Law,
    LawArticle,
    LawArticleVersion,
    OfficialLawArticleRecord,
    OfficialLawDocument as OfficialLawDocumentModel,
    OfficialLawIngestRun,
    OfficialLawSourceEvidence,
)
from app.schemas.official_law_source import OfficialLawCandidate, OfficialLawDocument, OfficialLawSearchResult
from app.services.legal_reference_service import PENDING_MOLEG_API_MAPPING, TODO_MOLEG_API_ARTICLE_CHECK
from app.services.moleg_live_client import (
    MOLEG_LAW_SEARCH_PATH,
    MOLEG_LAW_SERVICE_PATH,
    MOLEG_XML_TYPE,
    MolegLiveClient,
    parse_response,
    sanitized_url,
)
from app.services.moleg_probe_service import run_moleg_live_probes
from app.services.official_law_persistence_service import DOCUMENT_STATUS_NORMALIZED, DOCUMENT_STATUS_PARTIAL
from app.services.official_law_source import MolegOpenApiLawSourceProvider

SOURCE_PROVIDER = "moleg_open_api"
SOURCE_MODE = "live"
RUN_TYPE = "moleg_live_ingest"
LAW_SOURCE = "MOLEG_LIVE"
LAW_FAMILY_URBAN_DEVELOPMENT = "urban-development"
LAW_FAMILY_REGISTRY: dict[str, list[str]] = {
    LAW_FAMILY_URBAN_DEVELOPMENT: ["도시개발법", "도시개발법 시행령", "도시개발법 시행규칙"],
}
PARSER_VERSION = "moleg-live-ingest-v1"


@dataclass
class TableCounts:
    laws: int = 0
    law_articles: int = 0
    law_article_versions: int = 0
    official_law_documents: int = 0
    official_law_articles: int = 0
    official_law_ingest_runs: int = 0
    official_law_source_evidence: int = 0


@dataclass
class LiveIngestCounters:
    inserted_law_count: int = 0
    updated_law_count: int = 0
    skipped_law_count: int = 0
    inserted_law_version_count: int = 0
    updated_law_version_count: int = 0
    skipped_law_version_count: int = 0
    inserted_article_count: int = 0
    updated_article_count: int = 0
    skipped_article_count: int = 0
    inserted_article_version_count: int = 0
    updated_article_version_count: int = 0
    skipped_article_version_count: int = 0
    inserted_official_document_count: int = 0
    updated_official_document_count: int = 0
    skipped_official_document_count: int = 0
    inserted_official_article_count: int = 0
    updated_official_article_count: int = 0
    skipped_official_article_count: int = 0
    failed_count: int = 0


@dataclass
class MolegLiveIngestResult:
    requested_law_name: str
    dry_run: bool
    status: str
    final_reason_type: str
    selected_official_law_name: str | None = None
    selected_law_id: str | None = None
    selected_mst: str | None = None
    effective_dates: list[str] = field(default_factory=list)
    selected_endpoint: str | None = None
    trust_env: bool | None = None
    search_status: str = "not_run"
    detail_status: str = "not_run"
    parse_status: str = "not_run"
    selected_candidate_count: int = 0
    parsed_article_count: int = 0
    document_id: int | None = None
    ingest_run_id: int | None = None
    counters: LiveIngestCounters = field(default_factory=LiveIngestCounters)
    before_counts: TableCounts = field(default_factory=TableCounts)
    after_counts: TableCounts = field(default_factory=TableCounts)
    rollback: bool = False
    raw_payload_stored: bool = False
    secret_exposed: bool = False
    fallback_available: bool = True
    messages: list[str] = field(default_factory=list)
    history_status: str = "not_requested"
    version_statuses: list[dict[str, str | None]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "requested_law_name": self.requested_law_name,
            "selected_official_law_name": self.selected_official_law_name,
            "law_id": self.selected_law_id,
            "selected_mst": self.selected_mst,
            "effective_dates": self.effective_dates,
            "endpoint": self.selected_endpoint,
            "trust_env": self.trust_env,
            "search_status": self.search_status,
            "detail_status": self.detail_status,
            "parse_status": self.parse_status,
            "dry_run": self.dry_run,
            "inserted_law_count": self.counters.inserted_law_count,
            "updated_law_count": self.counters.updated_law_count,
            "skipped_law_count": self.counters.skipped_law_count,
            "inserted_law_version_count": self.counters.inserted_law_version_count,
            "updated_law_version_count": self.counters.updated_law_version_count,
            "skipped_law_version_count": self.counters.skipped_law_version_count,
            "inserted_article_count": self.counters.inserted_article_count,
            "updated_article_count": self.counters.updated_article_count,
            "skipped_article_count": self.counters.skipped_article_count,
            "inserted_article_version_count": self.counters.inserted_article_version_count,
            "updated_article_version_count": self.counters.updated_article_version_count,
            "skipped_article_version_count": self.counters.skipped_article_version_count,
            "inserted_official_document_count": self.counters.inserted_official_document_count,
            "updated_official_document_count": self.counters.updated_official_document_count,
            "skipped_official_document_count": self.counters.skipped_official_document_count,
            "inserted_official_article_count": self.counters.inserted_official_article_count,
            "updated_official_article_count": self.counters.updated_official_article_count,
            "skipped_official_article_count": self.counters.skipped_official_article_count,
            "failed_count": self.counters.failed_count,
            "rollback": self.rollback,
            "raw_payload_stored": self.raw_payload_stored,
            "secret_exposed": self.secret_exposed,
            "final_reason_type": self.final_reason_type,
            "status": self.status,
            "document_id": self.document_id,
            "ingest_run_id": self.ingest_run_id,
            "selected_candidate_count": self.selected_candidate_count,
            "parsed_article_count": self.parsed_article_count,
            "before_counts": self.before_counts.__dict__,
            "after_counts": self.after_counts.__dict__,
            "fallback_available": self.fallback_available,
            "messages": self.messages,
            "history_status": self.history_status,
            "version_statuses": self.version_statuses,
        }


def run_moleg_live_ingest(db: Session, law_name: str, dry_run: bool = True, force_rollback_after_persist: bool = False, include_history: int = 0) -> MolegLiveIngestResult:
    result = MolegLiveIngestResult(requested_law_name=law_name, dry_run=dry_run, status="started", final_reason_type="unknown_connection_error")
    result.before_counts = collect_table_counts(db)
    result.after_counts = result.before_counts
    try:
        diagnostic = run_moleg_live_probes(probe="matrix", query=law_name)
        result.selected_endpoint = diagnostic.selected_endpoint
        result.trust_env = _selected_trust_env(diagnostic.trust_env_probe)
        if diagnostic.final_reason_type != "ok" or not result.selected_endpoint:
            result.status = "source_error"
            result.final_reason_type = diagnostic.final_reason_type or diagnostic.reason_type
            result.messages.append(diagnostic.suggested_fix or diagnostic.next_action)
            return result

        client = MolegLiveClient(base_url=result.selected_endpoint, trust_env=bool(result.trust_env), retry_count=1)
        provider = MolegOpenApiLawSourceProvider(base_url=result.selected_endpoint, api_key=client.api_key, timeout_seconds=client.timeout_seconds)

        search_response = client._request(MOLEG_LAW_SEARCH_PATH, client.search_params(query=law_name, result_type=MOLEG_XML_TYPE, display=100, page=1))
        search_payload = parse_response(search_response).payload
        search_result = provider._normalize_law_search_result(payload=search_payload, query=law_name)
        selected_versions = select_law_version_candidates(search_result, law_name, include_history=include_history)
        result.search_status = "ok" if selected_versions else "unmatched"
        result.selected_candidate_count = len(search_result.candidates)
        if not selected_versions:
            result.status = "source_unavailable"
            result.final_reason_type = "invalid_response_format"
            result.messages.append("No exact law candidate with MST was found.")
            return result

        result.history_status = _history_status(selected_versions=selected_versions, include_history=include_history)
        documents: list[tuple[OfficialLawCandidate, OfficialLawDocument, str]] = []
        for selected, version_status in selected_versions:
            detail_response = client._request(
                MOLEG_LAW_SERVICE_PATH,
                client.document_params(selected.mst or "", result_type=MOLEG_XML_TYPE, ef_yd=_date_to_yyyymmdd(selected.enforcement_date)),
            )
            detail_payload = parse_response(detail_response).payload
            document = provider._normalize_law_document(payload=detail_payload, fallback_title=selected.title, fallback_mst=selected.mst)
            if document.enforcement_date is None:
                document.enforcement_date = selected.enforcement_date
            if document.law_id is None:
                document.law_id = selected.law_id
            if not document.articles:
                result.status = "source_error"
                result.final_reason_type = "invalid_response_format"
                result.messages.append(f"No article units were normalized for MST {selected.mst}.")
                return result
            documents.append((selected, document, version_status))

        first_selected, first_document, _ = documents[0]
        result.detail_status = "ok"
        result.parse_status = "ok"
        result.selected_official_law_name = first_selected.title
        result.selected_law_id = first_selected.law_id or first_document.law_id
        result.selected_mst = first_selected.mst
        result.effective_dates = sorted({item for _, document, _ in documents for item in [_date_to_yyyymmdd(document.enforcement_date)] if item})
        result.version_statuses = [
            {"mst": selected.mst, "effective_date": _date_to_yyyymmdd(document.enforcement_date or selected.enforcement_date), "version_status": version_status}
            for selected, document, version_status in documents
        ]
        result.parsed_article_count = sum(len(document.articles) for _, document, _ in documents)

        aggregate = LiveIngestCounters()
        for selected, document, version_status in documents:
            _add_counters(aggregate, plan_persistence(db=db, document=document, selected_candidate=selected, version_status=version_status))
        result.counters = aggregate
        if dry_run:
            result.status = "ready"
            result.final_reason_type = "ok"
            db.rollback()
            result.after_counts = collect_table_counts(db)
            return result

        run = _create_ingest_run(db=db, law_name=law_name)
        first_official_document: OfficialLawDocumentModel | None = None
        for selected, document, version_status in documents:
            official_document = sync_official_document(db=db, document=document, selected_candidate=selected, counters=result.counters)
            if first_official_document is None:
                first_official_document = official_document
            _sync_law_tables(db=db, document=document, selected_candidate=selected, counters=result.counters, version_status=version_status)
            _add_evidence(db=db, run=run, document=document, selected=selected, selected_endpoint=result.selected_endpoint, trust_env=result.trust_env, version_status=version_status)
        _complete_ingest_run(db=db, run=run, status="success", selected=first_selected, article_count=result.parsed_article_count, candidate_count=len(documents))
        if force_rollback_after_persist:
            raise RuntimeError("PHASE37_TEST_ROLLBACK")
        db.commit()
        result.status = "completed"
        result.final_reason_type = "ok"
        result.document_id = None if first_official_document is None else first_official_document.id
        result.ingest_run_id = run.id
        result.after_counts = collect_table_counts(db)
        return result
    except Exception as exc:
        db.rollback()
        result.counters.failed_count += 1
        result.rollback = not dry_run
        result.status = "rolled_back" if not dry_run else "source_error"
        result.final_reason_type = "rollback_test" if str(exc) == "PHASE37_TEST_ROLLBACK" else "unknown_connection_error"
        result.messages.append(exc.__class__.__name__)
        result.after_counts = collect_table_counts(db)
        return result
def collect_table_counts(db: Session) -> TableCounts:
    return TableCounts(
        laws=db.scalar(select(func.count()).select_from(Law)) or 0,
        law_articles=db.scalar(select(func.count()).select_from(LawArticle)) or 0,
        law_article_versions=db.scalar(select(func.count()).select_from(LawArticleVersion)) or 0,
        official_law_documents=db.scalar(select(func.count()).select_from(OfficialLawDocumentModel)) or 0,
        official_law_articles=db.scalar(select(func.count()).select_from(OfficialLawArticleRecord)) or 0,
        official_law_ingest_runs=db.scalar(select(func.count()).select_from(OfficialLawIngestRun)) or 0,
        official_law_source_evidence=db.scalar(select(func.count()).select_from(OfficialLawSourceEvidence)) or 0,
    )


def select_exact_law_candidate(search_result: OfficialLawSearchResult, law_name: str) -> OfficialLawCandidate | None:
    normalized = _normalize(law_name)
    candidates = [candidate for candidate in search_result.candidates if _normalize(candidate.title) == normalized and candidate.law_id and candidate.mst]
    if not candidates:
        return None
    candidates.sort(key=lambda item: (item.is_current is True, item.enforcement_date or date.min, item.match_score), reverse=True)
    return candidates[0]



def select_law_version_candidates(search_result: OfficialLawSearchResult, law_name: str, include_history: int = 0) -> list[tuple[OfficialLawCandidate, str]]:
    normalized = _normalize(law_name)
    exact = [candidate for candidate in search_result.candidates if _normalize(candidate.title) == normalized and candidate.law_id and candidate.mst and candidate.enforcement_date]
    if not exact:
        return []
    today = date.today()
    past_or_current = sorted([item for item in exact if item.enforcement_date and item.enforcement_date <= today], key=lambda item: (item.enforcement_date or date.min, item.mst or ""), reverse=True)
    scheduled = sorted([item for item in exact if item.enforcement_date and item.enforcement_date > today], key=lambda item: (item.enforcement_date or date.max, item.mst or ""))
    selected: list[tuple[OfficialLawCandidate, str]] = []
    if past_or_current:
        selected.append((past_or_current[0], "current"))
        for item in past_or_current[1:1 + max(0, include_history)]:
            selected.append((item, "historical"))
    elif scheduled:
        selected.append((scheduled[0], "scheduled"))
    for item in scheduled:
        if all(existing.mst != item.mst for existing, _ in selected):
            selected.append((item, "scheduled"))
    return selected


def _history_status(selected_versions: list[tuple[OfficialLawCandidate, str]], include_history: int) -> str:
    if include_history <= 0:
        return "not_requested"
    if any(status == "historical" for _, status in selected_versions):
        return "available"
    return "not_available_from_source"


def _add_counters(target: LiveIngestCounters, source: LiveIngestCounters) -> None:
    for field_name in target.__dataclass_fields__:
        setattr(target, field_name, getattr(target, field_name) + getattr(source, field_name))


@dataclass
class MolegLawFamilyIngestResult:
    law_family: str
    law_names: list[str]
    dry_run: bool
    include_history: int
    status: str
    transaction_policy: str
    results: list[MolegLiveIngestResult] = field(default_factory=list)
    before_counts: TableCounts = field(default_factory=TableCounts)
    after_counts: TableCounts = field(default_factory=TableCounts)
    raw_payload_stored: bool = False
    secret_exposed: bool = False
    fallback_available: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "law_family": self.law_family,
            "law_names": self.law_names,
            "dry_run": self.dry_run,
            "include_history": self.include_history,
            "status": self.status,
            "transaction_policy": self.transaction_policy,
            "results": [item.to_dict() for item in self.results],
            "before_counts": self.before_counts.__dict__,
            "after_counts": self.after_counts.__dict__,
            "raw_payload_stored": self.raw_payload_stored,
            "secret_exposed": self.secret_exposed,
            "fallback_available": self.fallback_available,
            "failed_laws": [item.requested_law_name for item in self.results if item.status not in {"ready", "completed"}],
        }


def run_moleg_law_family_ingest(db_factory: Any, law_family: str, dry_run: bool = True, include_history: int = 0, force_rollback_after_persist: bool = False) -> MolegLawFamilyIngestResult:
    law_names = LAW_FAMILY_REGISTRY.get(law_family)
    if not law_names:
        return MolegLawFamilyIngestResult(law_family=law_family, law_names=[], dry_run=dry_run, include_history=include_history, status="unknown_law_family", transaction_policy="per-law")
    before_db = db_factory()
    try:
        before_counts = collect_table_counts(before_db)
    finally:
        before_db.close()
    family_result = MolegLawFamilyIngestResult(law_family=law_family, law_names=law_names, dry_run=dry_run, include_history=include_history, status="started", transaction_policy="per-law", before_counts=before_counts, after_counts=before_counts)
    for law_name in law_names:
        db = db_factory()
        try:
            item = run_moleg_live_ingest(db=db, law_name=law_name, dry_run=dry_run, force_rollback_after_persist=force_rollback_after_persist, include_history=include_history)
            family_result.results.append(item)
        finally:
            db.close()
    after_db = db_factory()
    try:
        family_result.after_counts = collect_table_counts(after_db)
    finally:
        after_db.close()
    if all(item.status in {"ready", "completed"} for item in family_result.results):
        family_result.status = "ready" if dry_run else "completed"
    elif any(item.status in {"ready", "completed"} for item in family_result.results):
        family_result.status = "partial_success"
    else:
        family_result.status = "failed"
    return family_result
def plan_persistence(db: Session, document: OfficialLawDocument, selected_candidate: OfficialLawCandidate, version_status: str | None = None) -> LiveIngestCounters:
    counters = LiveIngestCounters()
    _plan_official_document(db, document, selected_candidate, counters)
    _plan_law_tables(db, document, selected_candidate, counters, version_status or _version_status(document.enforcement_date))
    return counters


def sync_official_document(db: Session, document: OfficialLawDocument, selected_candidate: OfficialLawCandidate, counters: LiveIngestCounters) -> OfficialLawDocumentModel:
    existing = _find_official_document(db, document, selected_candidate)
    values = _official_document_values(document, selected_candidate)
    if existing is None:
        existing = OfficialLawDocumentModel(**values)
        db.add(existing)
        db.flush()
    else:
        for key, value in values.items():
            setattr(existing, key, value)
        db.flush()
    _sync_official_articles(db, existing, document, counters)
    db.flush()
    return existing


def _plan_official_document(db: Session, document: OfficialLawDocument, selected: OfficialLawCandidate, counters: LiveIngestCounters) -> None:
    existing = _find_official_document(db, document, selected)
    if existing is None:
        counters.inserted_official_document_count += 1
        counters.inserted_official_article_count += len(document.articles)
        return
    values = _official_document_values(document, selected)
    if any(getattr(existing, key) != value for key, value in values.items() if key not in {"normalized_at"}):
        counters.updated_official_document_count += 1
    else:
        counters.skipped_official_document_count += 1
    existing_articles = _official_articles_by_key(db, existing.id)
    for index, article in enumerate(document.articles, start=1):
        key = _official_article_key(article.article_no, article.source_anchor, index)
        existing_article = existing_articles.get(key)
        if existing_article is None:
            counters.inserted_official_article_count += 1
        elif _official_article_changed(existing_article, article, index):
            counters.updated_official_article_count += 1
        else:
            counters.skipped_official_article_count += 1


def _sync_official_articles(db: Session, official_document: OfficialLawDocumentModel, document: OfficialLawDocument, counters: LiveIngestCounters) -> None:
    existing_articles = _official_articles_by_key(db, official_document.id)
    for index, article in enumerate(document.articles, start=1):
        key = _official_article_key(article.article_no, article.source_anchor, index)
        record = existing_articles.get(key)
        if record is None:
            record = OfficialLawArticleRecord(document_id=official_document.id, article_no=article.article_no, article_text=article.article_text)
            db.add(record)
            db.flush()
        record.article_title = article.article_title
        record.article_text = article.article_text
        record.paragraphs_json = article.paragraphs
        record.source_anchor = article.source_anchor
        record.source_hint = article.source_hint
        record.sort_order = index


def _plan_law_tables(db: Session, document: OfficialLawDocument, selected: OfficialLawCandidate, counters: LiveIngestCounters, version_status: str) -> None:
    law = _find_law(db, selected, document)
    if law is None:
        counters.inserted_law_count += 1
        counters.inserted_law_version_count += 1
        counters.inserted_article_count += len(document.articles)
        counters.inserted_article_version_count += len(document.articles)
        return
    law_values = _law_values(document, selected)
    if any(getattr(law, key) != value for key, value in law_values.items()):
        counters.updated_law_count += 1
    else:
        counters.skipped_law_count += 1
    counters.skipped_law_version_count += 1
    for index, article in enumerate(document.articles, start=1):
        existing_article = _find_law_article(db, law.id, article, index)
        if existing_article is None:
            counters.inserted_article_count += 1
            counters.inserted_article_version_count += 1
            continue
        article_values = _law_article_values(article, index)
        if any(getattr(existing_article, key) != value for key, value in article_values.items()):
            counters.updated_article_count += 1
        else:
            counters.skipped_article_count += 1
        existing_version = _find_article_version(db, existing_article.id, selected.mst, document.enforcement_date)
        if existing_version is None:
            counters.inserted_article_version_count += 1
        elif (
            existing_version.article_text != article.article_text
            or existing_version.version_status != version_status
            or existing_version.raw_payload_json is not None
        ):
            counters.updated_article_version_count += 1
        else:
            counters.skipped_article_version_count += 1


def _sync_law_tables(db: Session, document: OfficialLawDocument, selected_candidate: OfficialLawCandidate, counters: LiveIngestCounters, version_status: str | None = None) -> Law:
    law = _find_law(db, selected_candidate, document)
    if law is None:
        law = Law(**_law_values(document, selected_candidate))
        db.add(law)
        db.flush()
    else:
        for key, value in _law_values(document, selected_candidate).items():
            setattr(law, key, value)
    for index, article in enumerate(document.articles, start=1):
        law_article = _find_law_article(db, law.id, article, index)
        if law_article is None:
            law_article = LawArticle(law_id=law.id)
            db.add(law_article)
            db.flush()
        for key, value in _law_article_values(article, index).items():
            setattr(law_article, key, value)
        version = _find_article_version(db, law_article.id, selected_candidate.mst, document.enforcement_date)
        if version is None:
            version = LawArticleVersion(law_article_id=law_article.id)
            db.add(version)
            db.flush()
        version.effective_date = document.enforcement_date
        version.article_text = article.article_text
        version.raw_payload_json = null()
        version.source = _version_source(selected_candidate.mst)
        version.version_status = version_status or _version_status(document.enforcement_date)
    db.flush()
    return law


def _create_ingest_run(db: Session, law_name: str) -> OfficialLawIngestRun:
    run = OfficialLawIngestRun(run_type=RUN_TYPE, source_mode=SOURCE_MODE, query=law_name, status="started")
    db.add(run)
    db.flush()
    return run


def _complete_ingest_run(db: Session, run: OfficialLawIngestRun, status: str, selected: OfficialLawCandidate, article_count: int, candidate_count: int = 1) -> None:
    run.status = status
    run.selected_law_title = selected.title
    run.selected_law_id = selected.law_id
    run.selected_mst = selected.mst
    run.candidate_count = candidate_count
    run.article_count = article_count
    run.error_reason = None
    run.finished_at = datetime.now(UTC)


def _add_evidence(db: Session, run: OfficialLawIngestRun, document: OfficialLawDocument, selected: OfficialLawCandidate, selected_endpoint: str | None, trust_env: bool | None, version_status: str | None = None) -> None:
    db.add(OfficialLawSourceEvidence(
        ingest_run_id=run.id,
        evidence_type="moleg_live_ingest_summary",
        sanitized_summary_json={
            "source_type": SOURCE_PROVIDER,
            "source_name": "MOLEG Open API",
            "selected_official_law_name": selected.title,
            "law_id": selected.law_id,
            "mst": selected.mst,
            "effective_date": _date_to_yyyymmdd(document.enforcement_date or selected.enforcement_date),
            "selected_endpoint": selected_endpoint,
            "trust_env": trust_env,
            "article_count": len(document.articles),
            "version_status": version_status or _version_status(document.enforcement_date or selected.enforcement_date),
            "parser_version": PARSER_VERSION,
            "fetched_at": datetime.now(UTC).isoformat(),
            "raw_payload_stored": False,
            "secret_exposed": False,
        },
        raw_available=False,
        redaction_applied=True,
    ))


def _find_official_document(db: Session, document: OfficialLawDocument, selected: OfficialLawCandidate) -> OfficialLawDocumentModel | None:
    return db.scalar(select(OfficialLawDocumentModel).where(
        OfficialLawDocumentModel.source_provider == SOURCE_PROVIDER,
        OfficialLawDocumentModel.law_id == (document.law_id or selected.law_id),
        OfficialLawDocumentModel.mst == (document.mst or selected.mst),
        OfficialLawDocumentModel.enforcement_date == (document.enforcement_date or selected.enforcement_date),
    ))


def _official_document_values(document: OfficialLawDocument, selected: OfficialLawCandidate) -> dict[str, Any]:
    return {
        "source_provider": SOURCE_PROVIDER,
        "source_mode": SOURCE_MODE,
        "law_title": document.title,
        "law_short_title": selected.short_title,
        "law_id": document.law_id or selected.law_id,
        "mst": document.mst or selected.mst,
        "promulgation_date": selected.promulgation_date,
        "enforcement_date": document.enforcement_date or selected.enforcement_date,
        "is_current": selected.is_current,
        "document_status": DOCUMENT_STATUS_NORMALIZED if document.articles else DOCUMENT_STATUS_PARTIAL,
        "normalized_at": document.normalized_at,
        "provider_reason": document.provider_reason,
        "sanitized_source_url": document.sanitized_source_url,
    }


def _official_articles_by_key(db: Session, document_id: int) -> dict[tuple[int, str, str | None], OfficialLawArticleRecord]:
    return {_official_article_key(item.article_no, item.source_anchor, item.sort_order): item for item in db.scalars(select(OfficialLawArticleRecord).where(OfficialLawArticleRecord.document_id == document_id)).all()}


def _official_article_key(article_no: str, source_anchor: str | None, sort_order: int) -> tuple[int, str, str | None]:
    return (sort_order, article_no, source_anchor)


def _official_article_changed(record: OfficialLawArticleRecord, article: Any, sort_order: int) -> bool:
    return any([
        record.article_title != article.article_title,
        record.article_text != article.article_text,
        record.paragraphs_json != article.paragraphs,
        record.source_hint != article.source_hint,
        record.sort_order != sort_order,
    ])


def _find_law(db: Session, selected: OfficialLawCandidate, document: OfficialLawDocument) -> Law | None:
    return db.scalar(select(Law).where(Law.law_key == _law_key(document, selected)))


def _law_values(document: OfficialLawDocument, selected: OfficialLawCandidate) -> dict[str, Any]:
    return {
        "law_name": document.title,
        "law_key": _law_key(document, selected),
        "source": LAW_SOURCE,
        "mapping_status": PENDING_MOLEG_API_MAPPING,
    }


def _law_key(document: OfficialLawDocument, selected: OfficialLawCandidate) -> str:
    return f"moleg:{document.law_id or selected.law_id or selected.mst}"


def _find_law_article(db: Session, law_id: int, article: Any, sort_order: int) -> LawArticle | None:
    return db.scalar(select(LawArticle).where(LawArticle.law_id == law_id, LawArticle.article_key == _article_key(article, sort_order)))


def _law_article_values(article: Any, sort_order: int) -> dict[str, Any]:
    return {
        "article_key": _article_key(article, sort_order),
        "article_number_text": article.article_no,
        "article_title": article.article_title,
        "mapping_status": TODO_MOLEG_API_ARTICLE_CHECK,
    }


def _article_key(article: Any, sort_order: int) -> str:
    basis = f"{sort_order}|{article.article_no}|{article.source_anchor or ''}|{article.article_title or ''}"
    digest = hashlib.sha256(basis.encode("utf-8")).hexdigest()[:16]
    return f"moleg_article:{sort_order}:{digest}"


def _find_article_version(db: Session, article_id: int, mst: str | None, effective_date: date | None) -> LawArticleVersion | None:
    return db.scalar(select(LawArticleVersion).where(
        LawArticleVersion.law_article_id == article_id,
        LawArticleVersion.effective_date == effective_date,
        LawArticleVersion.source == _version_source(mst),
    ))


def _version_source(mst: str | None) -> str:
    return f"MOLEG_LIVE:{mst or 'UNKNOWN_MST'}"


def _version_status(effective_date: date | None) -> str:
    if effective_date is None:
        return "unknown_effective_date"
    today = date.today()
    return "scheduled" if effective_date > today else "current"


def _selected_trust_env(items: list[dict[str, Any]]) -> bool:
    for item in items:
        if item.get("selected_candidate") is True:
            return bool(item.get("trust_env"))
    return False


def _date_to_yyyymmdd(value: date | None) -> str | None:
    return value.strftime("%Y%m%d") if value else None


def _normalize(value: str) -> str:
    return " ".join(value.strip().casefold().split())


def sanitized_detail_url(base_url: str | None, mst: str | None, effective_date: date | None) -> str | None:
    if not base_url or not mst:
        return None
    client = MolegLiveClient(base_url=base_url, api_key="REDACTED")
    parsed = urlparse(base_url)
    safe_base = f"{parsed.scheme}://{parsed.netloc}" if parsed.scheme and parsed.netloc else base_url
    return sanitized_url(safe_base, MOLEG_LAW_SERVICE_PATH, client.document_params(mst, result_type=MOLEG_XML_TYPE, ef_yd=_date_to_yyyymmdd(effective_date)))
