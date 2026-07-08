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
        )
    except LawSourceProviderError:
        return _result(
            candidate=candidate,
            match_status=MATCH_STATUS_SOURCE_ERROR,
            can_promote_to_verified=False,
            reason="Official law source lookup failed. No secret values are included in this response.",
            source_mode=source_mode,
        )

    if official is None:
        return _result(
            candidate=candidate,
            match_status=MATCH_STATUS_UNMATCHED,
            can_promote_to_verified=False,
            reason="No official source article matched the candidate law name and article number.",
            source_mode=source_mode,
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
    provider = provider or make_law_source_provider(source_mode)
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

    return [
        verify_candidate_reference(reference=reference, provider=provider, source_mode=source_mode)
        for reference in db.scalars(statement).all()
    ]


def _result(
    candidate: CandidateLegalReferenceSnapshot,
    match_status: str,
    can_promote_to_verified: bool,
    reason: str,
    source_mode: str,
    official=None,
) -> LegalReferenceVerificationResult:
    return LegalReferenceVerificationResult(
        procedure_reference_id=candidate.procedure_reference_id,
        step_code=candidate.step_code,
        match_status=match_status,
        can_promote_to_verified=can_promote_to_verified,
        reason=reason,
        candidate_reference=candidate,
        official_source_snapshot=official,
        source_mode="live" if source_mode == "live" else "mock",
        provider_reason=reason,
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
