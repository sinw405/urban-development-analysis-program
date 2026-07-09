from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import ProcedureLegalReference
from app.schemas.official_law_source import (
    CandidateLegalReferenceSnapshot,
    LegalReferenceVerificationResult,
    MATCH_STATUS_MATCHED,
    MATCH_STATUS_PARTIAL,
    MATCH_STATUS_SOURCE_ERROR,
    MATCH_STATUS_SOURCE_UNAVAILABLE,
    MATCH_STATUS_UNMATCHED,
)
from app.services.legal_reference_service import LEGAL_REFERENCE_QUALITY_CANDIDATE
from app.services.official_law_db_source_service import OfficialLawDbSnapshotProvider
from app.services.official_law_source import (
    LawSourceProvider,
    LawSourceProviderError,
    LawSourceProviderUnavailable,
    MockOfficialLawSourceProvider,
    make_law_source_provider,
)


def build_candidate_snapshot(reference: ProcedureLegalReference) -> CandidateLegalReferenceSnapshot:
    law = reference.law
    article = reference.law_article
    notes = reference.notes_json or {}
    quality = notes.get("reference_quality") or LEGAL_REFERENCE_QUALITY_CANDIDATE

    return CandidateLegalReferenceSnapshot(
        procedure_reference_id=reference.id,
        step_code=reference.step_code,
        reference_quality=quality,
        reference_status=reference.reference_status,
        law_name=None if law is None else law.law_name,
        law_key=None if law is None else law.law_key,
        article_number_text=None if article is None else article.article_number_text,
        article_title=None if article is None else article.article_title,
        article_key=None if article is None else article.article_key,
    )


def verify_candidate_reference(
    reference: ProcedureLegalReference,
    provider: LawSourceProvider | None = None,
    source_mode: str = "mock",
    source_error: bool = False,
    reason_type: str | None = None,
) -> LegalReferenceVerificationResult:
    provider = provider or MockOfficialLawSourceProvider()
    candidate = build_candidate_snapshot(reference)

    if not candidate.law_name or not candidate.article_number_text:
        return _result(
            candidate=candidate,
            match_status=MATCH_STATUS_UNMATCHED,
            can_promote_to_verified=False,
            reason="Candidate reference does not contain both law name and article number.",
            source_mode=source_mode,
            source_error=source_error,
            reason_type=reason_type,
        )

    try:
        official = provider.get_article_by_law_and_article(candidate.law_name, candidate.article_number_text)
    except LawSourceProviderUnavailable:
        return _result(
            candidate=candidate,
            match_status=MATCH_STATUS_SOURCE_UNAVAILABLE,
            can_promote_to_verified=False,
            reason="Official law source is unavailable because live API configuration is missing or disabled.",
            source_mode=source_mode,
            source_error=source_error,
            reason_type=reason_type,
        )
    except LawSourceProviderError:
        return _result(
            candidate=candidate,
            match_status=MATCH_STATUS_SOURCE_ERROR,
            can_promote_to_verified=False,
            reason="Official law source lookup failed. No secret values are included in this response.",
            source_mode=source_mode,
            source_error=source_error,
            reason_type=reason_type,
        )

    if official is None:
        return _result(
            candidate=candidate,
            match_status=MATCH_STATUS_UNMATCHED,
            can_promote_to_verified=False,
            reason="No official source article matched the candidate law name and article number.",
            source_mode=source_mode,
            source_error=source_error,
            reason_type=reason_type,
        )

    title_matches = _has_title_or_keyword_match(candidate.article_title, official.article_title, official.article_text)
    has_source_url = bool(official.source_url)
    if title_matches and has_source_url:
        return _result(
            candidate=candidate,
            match_status=MATCH_STATUS_MATCHED,
            can_promote_to_verified=True,
            reason="Law name, article number, title or keyword, and official source URL matched.",
            official=official,
            source_mode=source_mode,
            source_error=source_error,
            reason_type=reason_type,
        )

    missing = []
    if not title_matches:
        missing.append("title_or_keyword")
    if not has_source_url:
        missing.append("source_url")
    return _result(
        candidate=candidate,
        match_status=MATCH_STATUS_PARTIAL,
        can_promote_to_verified=False,
        reason=f"Law name and article number matched, but {', '.join(missing)} did not match.",
        official=official,
        source_mode=source_mode,
    )


def list_verification_previews(
    db: Session,
    procedure_reference_ids: list[int] | None = None,
    provider: LawSourceProvider | None = None,
    source_mode: str = "mock",
) -> list[LegalReferenceVerificationResult]:
    statement = (
        select(ProcedureLegalReference)
        .options(
            joinedload(ProcedureLegalReference.law),
            joinedload(ProcedureLegalReference.law_article),
        )
        .order_by(ProcedureLegalReference.id)
    )
    if procedure_reference_ids is not None:
        statement = statement.where(ProcedureLegalReference.id.in_(procedure_reference_ids))

    references = db.scalars(statement).all()
    if provider is not None:
        return [verify_candidate_reference(reference=reference, provider=provider, source_mode=source_mode) for reference in references]

    results: list[LegalReferenceVerificationResult] = []
    db_provider = OfficialLawDbSnapshotProvider(db=db)
    for reference in references:
        db_result = verify_candidate_reference(reference=reference, provider=db_provider, source_mode="official_db")
        if db_result.match_status != MATCH_STATUS_UNMATCHED:
            results.append(db_result)
            continue

        live_error_type: str | None = None
        if source_mode == "live":
            live_result = verify_candidate_reference(reference=reference, provider=make_law_source_provider("live"), source_mode="live")
            if live_result.match_status not in {MATCH_STATUS_SOURCE_ERROR, MATCH_STATUS_SOURCE_UNAVAILABLE, MATCH_STATUS_UNMATCHED}:
                results.append(live_result)
                continue
            live_error_type = live_result.match_status

        fallback_result = verify_candidate_reference(
            reference=reference,
            provider=make_law_source_provider("mock"),
            source_mode="fallback" if live_error_type else "mock",
            source_error=live_error_type is not None,
            reason_type=live_error_type,
        )
        results.append(fallback_result)
    return results


def _result(
    candidate: CandidateLegalReferenceSnapshot,
    match_status: str,
    can_promote_to_verified: bool,
    reason: str,
    source_mode: str,
    official=None,
    source_error: bool = False,
    reason_type: str | None = None,
) -> LegalReferenceVerificationResult:
    return LegalReferenceVerificationResult(
        procedure_reference_id=candidate.procedure_reference_id,
        step_code=candidate.step_code,
        match_status=match_status,
        can_promote_to_verified=can_promote_to_verified,
        reason=reason,
        candidate_reference=candidate,
        official_source_snapshot=official,
        source_mode=source_mode if source_mode in {"official_db", "live", "mock", "fallback", "official_manual", "official_manual_db", "official_seed", "official_seed_db"} else "mock",
        provider_reason=reason,
        source_error=source_error or match_status in {MATCH_STATUS_SOURCE_ERROR, MATCH_STATUS_SOURCE_UNAVAILABLE},
        reason_type=reason_type or (match_status if match_status in {MATCH_STATUS_SOURCE_ERROR, MATCH_STATUS_SOURCE_UNAVAILABLE} else None),
        document_id=None if official is None else official.official_document_id,
        official_document_id=None if official is None else official.official_document_id,
        article_count=None if official is None else official.article_count,
        evidence_type=None if official is None else official.evidence_type,
        sanitized_url=None if official is None else official.source_url,
        source_hint=None if official is None else official.source_hint,
        source_mode_detail=None if official is None else official.source_mode_detail,
    )


def _has_title_or_keyword_match(
    candidate_title: str | None,
    official_title: str | None,
    official_text: str,
) -> bool:
    if not candidate_title:
        return False

    candidate_tokens = _tokens(candidate_title)
    official_tokens = _tokens(" ".join([official_title or "", official_text]))
    return bool(candidate_tokens & official_tokens)


def _tokens(value: str) -> set[str]:
    return {token for token in _normalize(value).replace("_", " ").split() if len(token) >= 3}


def _normalize(value: str) -> str:
    return " ".join(value.strip().casefold().split())
