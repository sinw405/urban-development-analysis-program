from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.models import OfficialLawArticleRecord, OfficialLawDocument, ProcedureOfficialArticleCandidate
from app.schemas.analyze import ProcedureArticleCandidate, ProcedureStep
from app.schemas.official_law_source import (
    ProcedureArticleCandidateActionResponse,
    ProcedureArticleCandidateConfirmationRequest,
    ProcedureArticleCandidateUnconfirmRequest,
)
from app.services.rule_loader import load_yaml_rule

MATCH_STATUS_CANDIDATE = "candidate"
MATCH_STATUS_WEAK = "weak_candidate"
MATCH_STATUS_NO_MATCH = "no_match"
MATCH_STATUS_NEEDS_REVIEW = "needs_review"
_ALLOWED_SOURCE_MODE_DETAILS = {"official_seed_db", "official_manual_db", "official_db", "fixture_only"}
_FORBIDDEN_EVIDENCE_KEYS = {"raw_payload", "raw_json", "raw_xml", "full_text"}


@dataclass
class ProcedureCandidateGroup:
    procedure_code: str
    procedure_name: str
    candidates: list[ProcedureArticleCandidate]


def resolve_procedure_article_candidates(
    db: Session,
    procedure_steps: list[ProcedureStep] | None = None,
    procedure_code: str | None = None,
    law_title: str | None = None,
    source_mode_detail: str | None = None,
    is_confirmed: bool | None = None,
    include_unmatched: bool = False,
    persist: bool = True,
) -> dict[str, Any]:
    configs = _load_keyword_configs()
    if procedure_steps:
        step_names = {step.step_code: step.step_name for step in procedure_steps}
        selected_configs = [_config_for_step(step.step_code, step.step_name, configs) for step in procedure_steps]
    else:
        step_names = {config["procedure_code"]: config.get("procedure_name", config["procedure_code"]) for config in configs}
        selected_configs = configs
    if procedure_code:
        selected_configs = [config for config in selected_configs if config["procedure_code"] == procedure_code]

    documents = _load_documents(db=db, law_title=law_title, source_mode_detail=source_mode_detail)
    groups: list[dict[str, Any]] = []
    unmatched_steps: list[dict[str, str]] = []
    warnings: list[str] = []

    for config in selected_configs:
        code = config["procedure_code"]
        name = step_names.get(code, config.get("procedure_name", code))
        candidates = _match_candidates_for_config(config=config, procedure_name=name, documents=documents)
        if persist:
            candidates = [_persist_candidate(db, candidate) for candidate in candidates]
            db.commit()
        candidates = _merge_persisted_candidates(
            db=db,
            procedure_code=code,
            candidates=candidates,
            law_title=law_title,
            source_mode_detail=source_mode_detail,
        )
        candidates = _sort_candidates(candidates)
        if is_confirmed is not None:
            candidates = [candidate for candidate in candidates if candidate.is_confirmed is is_confirmed]
        if candidates or include_unmatched:
            groups.append({"procedure_code": code, "procedure_name": name, "candidates": [candidate.model_dump() for candidate in candidates]})
        if not candidates:
            unmatched_steps.append({"procedure_code": code, "procedure_name": name, "match_status": MATCH_STATUS_NO_MATCH})
    if unmatched_steps:
        warnings.append("Some procedure steps have no official article candidates. This is not a legal determination.")

    return {"items": groups, "unmatched_steps": unmatched_steps, "warnings": warnings}


def confirm_procedure_article_candidate(
    db: Session,
    candidate_id: int,
    request: ProcedureArticleCandidateConfirmationRequest,
) -> ProcedureArticleCandidateActionResponse:
    candidate = db.get(ProcedureOfficialArticleCandidate, candidate_id)
    if candidate is None:
        raise HTTPException(status_code=404, detail="procedure article candidate not found")
    if not candidate.is_confirmed:
        candidate.confirmed_at = datetime.now(timezone.utc)
    elif candidate.confirmed_at is None:
        candidate.confirmed_at = datetime.now(timezone.utc)
    candidate.is_confirmed = True
    candidate.confirmed_by = request.confirmed_by or "manual_admin"
    candidate.confirmed_source = request.confirmed_source or "manual_admin"
    candidate.confirmation_note = request.confirmation_note
    db.commit()
    db.refresh(candidate)
    return _action_response(candidate=candidate, status="confirmed")


def unconfirm_procedure_article_candidate(
    db: Session,
    candidate_id: int,
    request: ProcedureArticleCandidateUnconfirmRequest,
) -> ProcedureArticleCandidateActionResponse:
    candidate = db.get(ProcedureOfficialArticleCandidate, candidate_id)
    if candidate is None:
        raise HTTPException(status_code=404, detail="procedure article candidate not found")
    candidate.is_confirmed = False
    candidate.confirmed_at = None
    candidate.confirmed_by = None
    candidate.confirmed_source = None
    candidate.confirmation_note = request.confirmation_note
    db.commit()
    db.refresh(candidate)
    return _action_response(candidate=candidate, status="unconfirmed")


def attach_article_candidates_to_analysis(db: Session, procedure_steps: list[ProcedureStep]) -> None:
    response = resolve_procedure_article_candidates(db=db, procedure_steps=procedure_steps, include_unmatched=True, persist=True)
    by_code = {item["procedure_code"]: [ProcedureArticleCandidate.model_validate(candidate) for candidate in item["candidates"]] for item in response["items"]}
    unmatched = {item["procedure_code"] for item in response["unmatched_steps"]}
    for step in procedure_steps:
        candidates = _sort_candidates(by_code.get(step.step_code, []))
        step.official_article_candidates = candidates
        step.legal_reference_candidates = candidates
        step.reference_candidate_count = len(candidates)
        if candidates:
            if any(candidate.is_confirmed for candidate in candidates):
                step.reference_status = "confirmed_reference_available"
            elif any(candidate.source_mode_detail == "fixture_only" for candidate in candidates):
                step.reference_status = "fixture_only"
            else:
                step.reference_status = "official_candidate_available"
        elif step.step_code in unmatched:
            step.reference_status = "no_official_candidate"
        else:
            step.reference_status = "needs_seed_data"


def get_candidate_diagnostic_counts(db: Session, analyze_step_codes: list[str] | None = None) -> dict[str, Any]:
    total = db.scalar(select(func.count()).select_from(ProcedureOfficialArticleCandidate)) or 0
    confirmed = db.scalar(select(func.count()).select_from(ProcedureOfficialArticleCandidate).where(ProcedureOfficialArticleCandidate.is_confirmed.is_(True))) or 0
    latest = db.scalar(select(ProcedureOfficialArticleCandidate).order_by(ProcedureOfficialArticleCandidate.created_at.desc(), ProcedureOfficialArticleCandidate.id.desc()).limit(1))
    latest_confirmed = db.scalar(
        select(ProcedureOfficialArticleCandidate)
        .where(ProcedureOfficialArticleCandidate.is_confirmed.is_(True), ProcedureOfficialArticleCandidate.confirmed_at.is_not(None))
        .order_by(ProcedureOfficialArticleCandidate.confirmed_at.desc(), ProcedureOfficialArticleCandidate.id.desc())
        .limit(1)
    )
    modes = list(db.scalars(select(ProcedureOfficialArticleCandidate.source_mode_detail).distinct().order_by(ProcedureOfficialArticleCandidate.source_mode_detail)).all())
    unmatched = 0
    has_analyze_steps = False
    if analyze_step_codes:
        matched_codes = set(db.scalars(select(ProcedureOfficialArticleCandidate.procedure_code).where(ProcedureOfficialArticleCandidate.procedure_code.in_(analyze_step_codes))).all())
        unmatched = len(set(analyze_step_codes) - matched_codes)
        has_analyze_steps = bool(matched_codes)
    return {
        "procedure_candidate_count": total,
        "confirmed_reference_count": confirmed,
        "unconfirmed_candidate_count": total - confirmed,
        "unmatched_procedure_count": unmatched,
        "candidate_source_modes": [mode for mode in modes if mode],
        "latest_candidate_generated_at": None if latest is None else latest.created_at,
        "latest_candidate_confirmed_at": None if latest_confirmed is None else latest_confirmed.confirmed_at,
        "confirmable_candidate_count": total - confirmed,
        "raw_payload_storage_violation_count": 0,
        "raw_payload_storage_policy_ok": True,
        "has_candidates_for_analyze_steps": has_analyze_steps,
    }


def validate_seed_candidate_items(items: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    for index, item in enumerate(items):
        label = f"items[{index}]"
        if not item.get("procedure_code"):
            errors.append(f"{label}: procedure_code is required")
        if not (item.get("law_name") or item.get("law_title")):
            errors.append(f"{label}: law_name or law_title is required")
        has_article_ref = any(item.get(key) for key in ["article_id", "article_no", "article_title", "article_anchor", "source_anchor"])
        if not has_article_ref:
            errors.append(f"{label}: article_id, article_no, article_title, article_anchor, or source_anchor is required")
        if item.get("source_mode_detail") not in _ALLOWED_SOURCE_MODE_DETAILS:
            errors.append(f"{label}: source_mode_detail must be one of {sorted(_ALLOWED_SOURCE_MODE_DETAILS)}")
        forbidden = sorted(_FORBIDDEN_EVIDENCE_KEYS.intersection(item.keys()))
        if forbidden:
            errors.append(f"{label}: forbidden raw payload fields are present: {', '.join(forbidden)}")
        if item.get("is_confirmed") is True and not (item.get("confirmed_by") or item.get("confirmed_source") or item.get("confirmation_note")):
            errors.append(f"{label}: confirmed seed candidates require confirmed_by, confirmed_source, or confirmation_note")
    return errors

def _merge_persisted_candidates(
    db: Session,
    procedure_code: str,
    candidates: list[ProcedureArticleCandidate],
    law_title: str | None,
    source_mode_detail: str | None,
) -> list[ProcedureArticleCandidate]:
    statement = select(ProcedureOfficialArticleCandidate).where(ProcedureOfficialArticleCandidate.procedure_code == procedure_code)
    if source_mode_detail:
        statement = statement.where(ProcedureOfficialArticleCandidate.source_mode_detail == source_mode_detail)
    if law_title:
        statement = statement.where(func.lower(ProcedureOfficialArticleCandidate.law_title).contains(_normalize(law_title)))
    merged = list(candidates)
    seen_ids = {candidate.id for candidate in merged if candidate.id is not None}
    for record in db.scalars(statement).all():
        if record.id not in seen_ids:
            merged.append(_candidate_from_record(record))
            seen_ids.add(record.id)
    return merged

def _load_keyword_configs() -> list[dict[str, Any]]:
    data = load_yaml_rule("procedure_article_keywords.yaml")
    steps = data.get("steps", [])
    return [step for step in steps if isinstance(step, dict) and step.get("procedure_code")]


def _config_for_step(step_code: str, step_name: str, configs: list[dict[str, Any]]) -> dict[str, Any]:
    for config in configs:
        if config.get("procedure_code") == step_code:
            return config
    return {"procedure_code": step_code, "procedure_name": step_name, "preferred_laws": [], "keywords": [step_name], "required": False}


def _load_documents(db: Session, law_title: str | None, source_mode_detail: str | None) -> list[OfficialLawDocument]:
    statement = select(OfficialLawDocument).options(joinedload(OfficialLawDocument.articles)).where(OfficialLawDocument.document_status.in_(["normalized", "partial"]))
    if law_title:
        normalized = _normalize(law_title)
        statement = statement.where(func.lower(OfficialLawDocument.law_title).contains(normalized))
    documents = db.scalars(statement).unique().all()
    if source_mode_detail:
        documents = [document for document in documents if _source_mode_detail(document.source_mode) == source_mode_detail]
    return documents


def _match_candidates_for_config(config: dict[str, Any], procedure_name: str, documents: list[OfficialLawDocument]) -> list[ProcedureArticleCandidate]:
    preferred_laws = [_normalize(value) for value in config.get("preferred_laws", [])]
    keywords = [str(value).strip() for value in config.get("keywords", []) if str(value).strip()]
    candidates: list[ProcedureArticleCandidate] = []
    for document in documents:
        if preferred_laws and _normalize(document.law_title) not in preferred_laws and _normalize(document.law_short_title or "") not in preferred_laws:
            continue
        for article in document.articles:
            candidate = _score_article(config=config, procedure_name=procedure_name, document=document, article=article, keywords=keywords)
            if candidate is not None:
                candidates.append(candidate)
    return _sort_candidates(candidates)[:5]


def _score_article(config: dict[str, Any], procedure_name: str, document: OfficialLawDocument, article: OfficialLawArticleRecord, keywords: list[str]) -> ProcedureArticleCandidate | None:
    title_blob = _normalize(article.article_title or "")
    text_blob = _normalize(article.article_text or "")
    anchor_blob = _normalize(" ".join([article.source_anchor or "", article.source_hint or ""]))
    matched_title = [keyword for keyword in keywords if _normalize(keyword) and _normalize(keyword) in title_blob]
    matched_text = [keyword for keyword in keywords if _normalize(keyword) and _normalize(keyword) in text_blob]
    matched_anchor = [keyword for keyword in keywords if _normalize(keyword) and _normalize(keyword) in anchor_blob]
    if matched_title:
        method = "title_keyword"
        score = 90.0
    elif matched_anchor:
        method = "article_anchor"
        score = 70.0
    elif matched_text:
        method = "text_keyword"
        score = 60.0
    elif document.source_mode in {"fixture", "mock"}:
        method = "fixture_only"
        score = 20.0
    else:
        return None
    source_detail = _source_mode_detail(document.source_mode)
    return ProcedureArticleCandidate(
        procedure_code=config["procedure_code"],
        procedure_name=procedure_name,
        article_id=article.id,
        document_id=document.id,
        law_title=document.law_title,
        law_short_title=document.law_short_title,
        law_id=document.law_id,
        mst=document.mst,
        article_no=article.article_no,
        article_title=article.article_title,
        article_anchor=article.source_anchor,
        match_method=method,
        match_score=score,
        match_status=MATCH_STATUS_CANDIDATE if score >= 60 else MATCH_STATUS_WEAK,
        confidence_level=_confidence(document.source_mode, score),
        source_mode="official_db" if document.source_mode in {"official_seed", "official_manual", "live", "fixture"} else document.source_mode,
        source_mode_detail=source_detail,
        is_confirmed=False,
    )


def _persist_candidate(db: Session, candidate: ProcedureArticleCandidate) -> ProcedureArticleCandidate:
    existing = db.scalar(
        select(ProcedureOfficialArticleCandidate).where(
            ProcedureOfficialArticleCandidate.procedure_code == candidate.procedure_code,
            ProcedureOfficialArticleCandidate.article_id == candidate.article_id,
            ProcedureOfficialArticleCandidate.match_method == candidate.match_method,
            ProcedureOfficialArticleCandidate.source_mode_detail == candidate.source_mode_detail,
        )
    )
    if existing is None:
        existing = db.scalar(
            select(ProcedureOfficialArticleCandidate).where(
                ProcedureOfficialArticleCandidate.procedure_code == candidate.procedure_code,
                ProcedureOfficialArticleCandidate.article_id == candidate.article_id,
                ProcedureOfficialArticleCandidate.source_mode_detail == candidate.source_mode_detail,
                ProcedureOfficialArticleCandidate.is_confirmed.is_(True),
            )
        )
    if existing is None:
        existing = ProcedureOfficialArticleCandidate()
        db.add(existing)
    existing.procedure_code = candidate.procedure_code
    existing.procedure_name = candidate.procedure_name
    existing.law_title = candidate.law_title
    existing.law_short_title = candidate.law_short_title
    existing.law_id = candidate.law_id
    existing.mst = candidate.mst
    existing.document_id = candidate.document_id
    existing.article_id = candidate.article_id
    existing.article_no = candidate.article_no
    existing.article_title = candidate.article_title
    existing.article_anchor = candidate.article_anchor
    existing.match_method = candidate.match_method
    existing.match_score = candidate.match_score
    existing.match_status = candidate.match_status
    existing.source_mode = candidate.source_mode
    existing.source_mode_detail = candidate.source_mode_detail
    existing.confidence_level = candidate.confidence_level
    existing.provider_reason = "Generated as an unconfirmed official article candidate. Expert review required."
    db.flush()
    return _candidate_from_record(existing)


def _candidate_from_record(record: ProcedureOfficialArticleCandidate) -> ProcedureArticleCandidate:
    return ProcedureArticleCandidate(
        id=record.id,
        procedure_code=record.procedure_code,
        procedure_name=record.procedure_name,
        article_id=record.article_id,
        document_id=record.document_id,
        law_title=record.law_title,
        law_short_title=record.law_short_title,
        law_id=record.law_id,
        mst=record.mst,
        article_no=record.article_no,
        article_title=record.article_title,
        article_anchor=record.article_anchor,
        match_method=record.match_method,
        match_score=record.match_score,
        match_status=record.match_status,
        confidence_level=record.confidence_level,
        source_mode=record.source_mode,
        source_mode_detail=record.source_mode_detail,
        is_confirmed=record.is_confirmed,
        generated_at=record.created_at,
        confirmed_at=record.confirmed_at,
        confirmed_by=record.confirmed_by,
        confirmed_source=record.confirmed_source,
        confirmation_note=record.confirmation_note,
    )


def _action_response(candidate: ProcedureOfficialArticleCandidate, status: str) -> ProcedureArticleCandidateActionResponse:
    return ProcedureArticleCandidateActionResponse(
        candidate_id=candidate.id,
        procedure_code=candidate.procedure_code,
        is_confirmed=candidate.is_confirmed,
        confirmed_at=candidate.confirmed_at,
        confirmed_by=candidate.confirmed_by,
        confirmed_source=candidate.confirmed_source,
        confirmation_note=candidate.confirmation_note,
        status=status,
        secret_exposed=False,
    )


def _sort_candidates(candidates: list[ProcedureArticleCandidate]) -> list[ProcedureArticleCandidate]:
    return sorted(candidates, key=lambda item: (not item.is_confirmed, -item.match_score, item.id or 0))


def _source_mode_detail(source_mode: str | None) -> str:
    if source_mode == "official_seed":
        return "official_seed_db"
    if source_mode == "official_manual":
        return "official_manual_db"
    if source_mode in {"fixture", "mock"}:
        return "fixture_only"
    return "official_db"


def _confidence(source_mode: str | None, score: float) -> str:
    if source_mode in {"fixture", "mock"}:
        return "low"
    if score >= 85:
        return "high"
    if score >= 60:
        return "medium"
    return "low"


def _normalize(value: str) -> str:
    return " ".join(value.strip().casefold().split())
