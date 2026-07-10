from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlparse

import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import OfficialLawArticleRecord, OfficialLawDocument, ProcedureOfficialArticleCandidate
from app.services.official_law_persistence_service import (
    INGEST_STATUS_SUCCESS,
    add_source_evidence,
    complete_ingest_run,
    create_ingest_run,
)
from app.services.rule_loader import load_yaml_rule

DEFAULT_SEED_DIR = Path(__file__).resolve().parents[3] / "data" / "official_law_seeds"
ALLOWED_LAW_TYPES = {"act", "enforcement_decree", "enforcement_rule", "other"}
ALLOWED_SOURCE_TYPES = {"official_manual"}
ALLOWED_SOURCE_MODE_DETAILS = {"official_seed_db", "official_manual_db"}
ALLOWED_ARTICLE_STATUSES = {"current", "scheduled", "historical", "unknown"}
FORBIDDEN_FIELDS = {"raw_payload", "raw_json", "raw_xml", "full_text", "article_full_text", "original_body", "body", "content_raw"}
SENSITIVE_QUERY_KEYS = {"servicekey", "service_key", "oc", "key", "api_key", "apikey", "token", "access_token", "secret", "client_secret"}
SEED_SOURCE_PROVIDER = "manual_official_seed"
SEED_SOURCE_MODE = "official_seed"
SEED_SOURCE_MODE_DETAIL = "official_seed_db"
SEED_EVIDENCE_TYPE = "manual_official_seed_summary"


@dataclass
class SeedFileValidation:
    path: str
    law_key: str | None = None
    law_name: str | None = None
    law_type: str | None = None
    status: str = "unknown"
    article_count: int = 0
    confirmed_count: int = 0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    is_example: bool = False


@dataclass
class SeedValidationReport:
    status: str
    seed_directory: str
    seed_directory_exists: bool
    total_files: int = 0
    valid_files: int = 0
    empty_files: int = 0
    skipped_files: int = 0
    total_articles: int = 0
    confirmed_articles: int = 0
    rejected_count: int = 0
    raw_payload_policy_ok: bool = True
    secret_exposed: bool = False
    files: list[SeedFileValidation] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "seed_directory": self.seed_directory,
            "seed_directory_exists": self.seed_directory_exists,
            "total_files": self.total_files,
            "valid_files": self.valid_files,
            "empty_files": self.empty_files,
            "skipped_files": self.skipped_files,
            "total_articles": self.total_articles,
            "confirmed_articles": self.confirmed_articles,
            "rejected_count": self.rejected_count,
            "raw_payload_policy_ok": self.raw_payload_policy_ok,
            "secret_exposed": self.secret_exposed,
            "seed_files": [file.__dict__ for file in self.files],
            "errors": self.errors,
            "warnings": self.warnings,
        }


def validate_official_law_seed_directory(seed_dir: Path | str = DEFAULT_SEED_DIR, include_examples: bool = True) -> SeedValidationReport:
    directory = Path(seed_dir)
    report = SeedValidationReport(status="ok", seed_directory=str(directory), seed_directory_exists=directory.exists())
    if not directory.exists():
        report.status = "missing"
        report.errors.append("seed directory does not exist")
        report.rejected_count = 1
        return report

    files = sorted(directory.glob("*.seed.yaml"))
    if include_examples:
        files.extend(sorted((directory / "examples").glob("*.yaml")))
    report.total_files = len(files)
    procedure_codes = _procedure_codes()
    for file_path in files:
        result, payload = validate_official_law_seed_file(file_path, procedure_codes=procedure_codes)
        report.files.append(result)
        report.total_articles += result.article_count
        report.confirmed_articles += result.confirmed_count
        if result.status == "valid":
            report.valid_files += 1
        elif result.status == "empty_valid":
            report.empty_files += 1
            report.valid_files += 1
        elif result.status == "skipped":
            report.skipped_files += 1
        else:
            report.rejected_count += 1
            report.errors.extend([f"{result.path}: {error}" for error in result.errors])
    report.raw_payload_policy_ok = report.rejected_count == 0 or not any(_mentions_forbidden(error) for error in report.errors)
    report.secret_exposed = False
    if report.rejected_count:
        report.status = "failed"
    elif report.empty_files and report.valid_files == report.empty_files and report.total_articles == 0:
        report.status = "empty_valid"
    return report


def validate_official_law_seed_file(path: Path, procedure_codes: set[str] | None = None) -> tuple[SeedFileValidation, dict[str, Any] | None]:
    result = SeedFileValidation(path=str(path), is_example="examples" in path.parts)
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        result.status = "invalid"
        result.errors.append(f"yaml parse failed: {exc.__class__.__name__}")
        return result, None
    if payload is None:
        result.status = "empty_valid"
        return result, None
    if not isinstance(payload, dict):
        result.status = "invalid"
        result.errors.append("seed root must be a mapping")
        return result, None

    result.law_key = _text(payload.get("law_key"))
    result.law_name = _text(payload.get("law_name"))
    result.law_type = _text(payload.get("law_type"))
    errors = _validate_payload(payload, procedure_codes or _procedure_codes())
    articles = payload.get("articles") or []
    if isinstance(articles, list):
        result.article_count = len(articles)
        result.confirmed_count = sum(1 for article in articles if isinstance(article, dict) and article.get("is_confirmed") is True)
    result.errors.extend(errors)
    if errors:
        result.status = "invalid"
    elif result.article_count == 0:
        result.status = "empty_valid"
    else:
        result.status = "valid"
    return result, payload


def import_official_law_seed_directory(db: Session, seed_dir: Path | str = DEFAULT_SEED_DIR) -> dict[str, Any]:
    validation = validate_official_law_seed_directory(seed_dir=seed_dir, include_examples=False)
    if validation.rejected_count:
        return {
            "status": "validation_error",
            "files_scanned": validation.total_files,
            "files_imported": 0,
            "empty_files": validation.empty_files,
            "articles_imported": 0,
            "candidates_created": 0,
            "candidates_confirmed": 0,
            "raw_payload_policy_ok": validation.raw_payload_policy_ok,
            "secret_exposed": False,
            "errors": validation.errors,
            "warnings": validation.warnings,
        }

    files_imported = 0
    articles_imported = 0
    candidates_created = 0
    candidates_confirmed = 0
    procedure_names = _procedure_names()
    for file_result in validation.files:
        if file_result.status != "valid":
            continue
        _, payload = validate_official_law_seed_file(Path(file_result.path), procedure_codes=set(procedure_names))
        if payload is None:
            continue
        imported = _import_payload(db=db, payload=payload, procedure_names=procedure_names)
        files_imported += 1
        articles_imported += imported["articles_imported"]
        candidates_created += imported["candidates_created"]
        candidates_confirmed += imported["candidates_confirmed"]
    db.commit()
    return {
        "status": "ok",
        "files_scanned": validation.total_files,
        "files_imported": files_imported,
        "empty_files": validation.empty_files,
        "articles_imported": articles_imported,
        "candidates_created": candidates_created,
        "candidates_confirmed": candidates_confirmed,
        "raw_payload_policy_ok": True,
        "secret_exposed": False,
        "errors": [],
        "warnings": validation.warnings,
    }


def seed_status(seed_dir: Path | str = DEFAULT_SEED_DIR) -> dict[str, Any]:
    report = validate_official_law_seed_directory(seed_dir=seed_dir, include_examples=False)
    return {
        "seed_directory_exists": report.seed_directory_exists,
        "seed_files": [
            {
                "law_key": item.law_key,
                "law_name": item.law_name,
                "law_type": item.law_type,
                "status": item.status,
                "article_count": item.article_count,
                "confirmed_count": item.confirmed_count,
                "errors": item.errors,
                "warnings": item.warnings,
            }
            for item in report.files
        ],
        "total_files": report.total_files,
        "valid_files": report.valid_files,
        "empty_files": report.empty_files,
        "total_articles": report.total_articles,
        "confirmed_articles": report.confirmed_articles,
        "validation_status": report.status,
        "raw_payload_policy_ok": report.raw_payload_policy_ok,
        "secret_exposed": False,
    }


def _import_payload(db: Session, payload: dict[str, Any], procedure_names: dict[str, str]) -> dict[str, int]:
    source = payload.get("source") or {}
    articles = payload.get("articles") or []
    law_key = _text(payload.get("law_key")) or "unknown_seed_law"
    law_name = _text(payload.get("law_name")) or law_key
    document = _upsert_document(db=db, payload=payload, source=source, law_key=law_key, law_name=law_name)
    run = create_ingest_run(db=db, query=law_name, source_mode=SEED_SOURCE_MODE, run_type="manual_official_seed_import")
    imported_articles = 0
    candidates_created = 0
    candidates_confirmed = 0
    for index, article_payload in enumerate(articles, start=1):
        article = _upsert_article(db=db, document=document, article_payload=article_payload, sort_order=index)
        imported_articles += 1
        for procedure_code in article_payload.get("procedure_codes") or []:
            candidate, created = _upsert_candidate(db=db, document=document, article=article, article_payload=article_payload, procedure_code=procedure_code, procedure_name=procedure_names.get(procedure_code, procedure_code))
            if created:
                candidates_created += 1
            if candidate.is_confirmed:
                candidates_confirmed += 1
    complete_ingest_run(db=db, run=run, status=INGEST_STATUS_SUCCESS, error_reason=None)
    add_source_evidence(
        db=db,
        run=run,
        evidence_type=SEED_EVIDENCE_TYPE,
        summary={
            "law_key": law_key,
            "law_name": law_name,
            "article_count": imported_articles,
            "confirmed_count": sum(1 for item in articles if item.get("is_confirmed") is True),
            "source_name": source.get("source_name"),
            "source_type": source.get("source_type"),
            "source_url_optional": _safe_url(source.get("source_url_optional")),
        },
        raw_available=False,
    )
    return {"articles_imported": imported_articles, "candidates_created": candidates_created, "candidates_confirmed": candidates_confirmed}


def _upsert_document(db: Session, payload: dict[str, Any], source: dict[str, Any], law_key: str, law_name: str) -> OfficialLawDocument:
    document = db.scalar(select(OfficialLawDocument).where(OfficialLawDocument.source_provider == SEED_SOURCE_PROVIDER, OfficialLawDocument.law_id == law_key, OfficialLawDocument.mst == law_key))
    if document is None:
        document = OfficialLawDocument(source_provider=SEED_SOURCE_PROVIDER, source_mode=SEED_SOURCE_MODE, law_title=law_name, law_id=law_key, mst=law_key, document_status="normalized", normalized_at=datetime.now(UTC), sanitized_source_url=_safe_url(source.get("source_url_optional")) or "manual-official-seed://sanitized")
        db.add(document)
    document.source_mode = SEED_SOURCE_MODE
    document.law_title = law_name
    document.law_short_title = None
    document.law_id = law_key
    document.mst = law_key
    document.enforcement_date = None
    document.promulgation_date = None
    document.is_current = None
    document.document_status = "normalized"
    document.normalized_at = datetime.now(UTC)
    document.provider_reason = "Manual official seed sanitized summary. Full article body and raw payload are not stored."
    document.sanitized_source_url = _safe_url(source.get("source_url_optional")) or "manual-official-seed://sanitized"
    db.flush()
    return document


def _upsert_article(db: Session, document: OfficialLawDocument, article_payload: dict[str, Any], sort_order: int) -> OfficialLawArticleRecord:
    article_no = _text(article_payload.get("article_no")) or _text(article_payload.get("article_key")) or "UNKNOWN_ARTICLE_REFERENCE"
    anchor = _text(article_payload.get("article_anchor"))
    article = db.scalar(select(OfficialLawArticleRecord).where(OfficialLawArticleRecord.document_id == document.id, OfficialLawArticleRecord.article_no == article_no, OfficialLawArticleRecord.source_anchor == anchor))
    if article is None:
        article = OfficialLawArticleRecord(document_id=document.id, article_no=article_no, article_text="")
        db.add(article)
    article.article_no = article_no
    article.article_title = _text(article_payload.get("article_title"))
    article.article_text = _text(article_payload.get("sanitized_summary")) or "SANITIZED_SUMMARY_NOT_PROVIDED"
    article.paragraphs_json = []
    article.source_anchor = anchor
    article.source_hint = "Manual official seed anchor/reference only; full article text is not stored."
    article.sort_order = sort_order
    db.flush()
    return article


def _upsert_candidate(db: Session, document: OfficialLawDocument, article: OfficialLawArticleRecord, article_payload: dict[str, Any], procedure_code: str, procedure_name: str) -> tuple[ProcedureOfficialArticleCandidate, bool]:
    candidate = db.scalar(select(ProcedureOfficialArticleCandidate).where(ProcedureOfficialArticleCandidate.procedure_code == procedure_code, ProcedureOfficialArticleCandidate.article_id == article.id, ProcedureOfficialArticleCandidate.match_method == "manual_seed_procedure_code", ProcedureOfficialArticleCandidate.source_mode_detail == SEED_SOURCE_MODE_DETAIL))
    created = candidate is None
    if candidate is None:
        candidate = ProcedureOfficialArticleCandidate()
        db.add(candidate)
    candidate.procedure_code = procedure_code
    candidate.procedure_name = procedure_name
    candidate.law_title = document.law_title
    candidate.law_short_title = document.law_short_title
    candidate.law_id = document.law_id
    candidate.mst = document.mst
    candidate.document_id = document.id
    candidate.article_id = article.id
    candidate.article_no = article.article_no
    candidate.article_title = article.article_title
    candidate.article_anchor = article.source_anchor
    candidate.match_method = "manual_seed_procedure_code"
    candidate.match_score = float(article_payload.get("confidence") or 0.7) * 100
    candidate.match_status = "candidate"
    candidate.source_mode = "official_db"
    candidate.source_mode_detail = SEED_SOURCE_MODE_DETAIL
    candidate.confidence_level = _confidence_label(float(article_payload.get("confidence") or 0.7))
    candidate.provider_reason = "Generated from reviewed manual official seed metadata. Expert review may still be required."
    if article_payload.get("is_confirmed") is True:
        candidate.is_confirmed = True
        candidate.confirmed_at = candidate.confirmed_at or datetime.now(UTC)
        candidate.confirmed_by = _text(article_payload.get("confirmed_by")) or "manual_seed"
        candidate.confirmed_source = "manual_official_seed"
        candidate.confirmation_note = _text(article_payload.get("confirmation_note"))
    db.flush()
    return candidate, created


def _validate_payload(payload: dict[str, Any], procedure_codes: set[str]) -> list[str]:
    errors: list[str] = []
    _find_forbidden_fields(payload, "root", errors)
    for key in ("seed_version", "law_key", "law_name", "law_type"):
        if not payload.get(key):
            errors.append(f"{key} is required")
    if payload.get("law_type") not in ALLOWED_LAW_TYPES:
        errors.append(f"law_type must be one of {sorted(ALLOWED_LAW_TYPES)}")
    source = payload.get("source")
    if not isinstance(source, dict):
        errors.append("source mapping is required")
        source = {}
    if source.get("source_type") not in ALLOWED_SOURCE_TYPES:
        errors.append(f"source.source_type must be one of {sorted(ALLOWED_SOURCE_TYPES)}")
    url = source.get("source_url_optional")
    if url and _has_sensitive_query(url):
        errors.append("source.source_url_optional contains a sensitive query parameter")
    articles = payload.get("articles")
    if articles is None:
        errors.append("articles is required; use [] for an empty seed")
        return errors
    if not isinstance(articles, list):
        errors.append("articles must be a list")
        return errors
    for index, article in enumerate(articles):
        label = f"articles[{index}]"
        if not isinstance(article, dict):
            errors.append(f"{label} must be a mapping")
            continue
        _find_forbidden_fields(article, label, errors)
        if not any(article.get(key) for key in ("article_key", "article_no", "article_title", "article_anchor")):
            errors.append(f"{label}: one of article_key/article_no/article_title/article_anchor is required")
        if not article.get("sanitized_summary"):
            errors.append(f"{label}: sanitized_summary is required")
        if article.get("status") not in ALLOWED_ARTICLE_STATUSES:
            errors.append(f"{label}: status must be one of {sorted(ALLOWED_ARTICLE_STATUSES)}")
        if article.get("source_mode_detail") not in ALLOWED_SOURCE_MODE_DETAILS:
            errors.append(f"{label}: source_mode_detail must be one of {sorted(ALLOWED_SOURCE_MODE_DETAILS)}")
        confidence = article.get("confidence")
        if not isinstance(confidence, (int, float)) or not 0 <= float(confidence) <= 1:
            errors.append(f"{label}: confidence must be a number between 0 and 1")
        for procedure_code in article.get("procedure_codes") or []:
            if procedure_code not in procedure_codes:
                errors.append(f"{label}: unknown procedure_code {procedure_code}")
        if article.get("is_confirmed") is True and not (article.get("confirmation_note") or (source or {}).get("verified_by_optional")):
            errors.append(f"{label}: confirmed articles require confirmation_note or source.verified_by_optional")
    return errors


def _find_forbidden_fields(value: Any, path: str, errors: list[str]) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key) in FORBIDDEN_FIELDS:
                errors.append(f"{path}: forbidden field {key} is present")
            _find_forbidden_fields(item, f"{path}.{key}", errors)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _find_forbidden_fields(item, f"{path}[{index}]", errors)


def _has_sensitive_query(url: str) -> bool:
    parsed = urlparse(str(url))
    return any(key.lower() in SENSITIVE_QUERY_KEYS for key, _ in parse_qsl(parsed.query, keep_blank_values=True))


def _safe_url(url: Any) -> str | None:
    if not url:
        return None
    parsed = urlparse(str(url))
    if not parsed.scheme or not parsed.netloc:
        return None
    return parsed._replace(query="", fragment="").geturl()


def _procedure_codes() -> set[str]:
    return set(_procedure_names())


def _procedure_names() -> dict[str, str]:
    rules = load_yaml_rule("procedure_rules.yaml")
    result: dict[str, str] = {}
    for step in rules.get("procedures", []):
        if isinstance(step, dict) and step.get("step_code"):
            result[str(step["step_code"])] = str(step.get("step_name") or step["step_code"])
    for step in rules.get("common_steps", []):
        if isinstance(step, dict) and step.get("step_code"):
            result[str(step["step_code"])] = str(step.get("step_name") or step["step_code"])
    for step in rules.get("conditional_steps", []):
        if isinstance(step, dict) and step.get("step_code"):
            result[str(step["step_code"])] = str(step.get("step_name") or step["step_code"])
    for step in rules.get("steps", []):
        if isinstance(step, dict) and step.get("step_code"):
            result[str(step["step_code"])] = str(step.get("step_name") or step["step_code"])
    return result


def _confidence_label(confidence: float) -> str:
    if confidence >= 0.85:
        return "high"
    if confidence >= 0.6:
        return "medium"
    return "low"


def _parse_date(value: Any) -> date | None:
    if not value:
        return None
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _mentions_forbidden(value: str) -> bool:
    lowered = value.lower()
    return any(field in lowered for field in FORBIDDEN_FIELDS)

