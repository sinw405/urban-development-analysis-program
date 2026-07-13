from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any
import hashlib

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import LawChangeImpactEvent, OfficialLawArticleRecord, OfficialLawDocument, ProcedureOfficialArticleCandidate
from app.schemas.analyze import ProcedureArticleCandidate
from app.services.moleg_version_diff_service import ArticleDiffItem, diff_moleg_versions
from app.services.procedure_article_candidate_service import resolve_procedure_article_candidates
from app.services.procedure_article_review_service import REVIEW_SOURCE_REJECTED
from app.services.rule_loader import load_yaml_rule

IMPACT_HIGH = "high"
IMPACT_MEDIUM = "medium"
IMPACT_INFORMATIONAL = "informational"
STATUS_CONFIRMED = "confirmed"
STATUS_UNCONFIRMED = "unconfirmed"
STATUS_REJECTED = "rejected"
STATUS_NEEDS_REVALIDATION = "needs_revalidation"
STATUS_STALE = "stale"
STATUS_UNMAPPED = "unmapped"


@dataclass
class ImpactEventPlan:
    law_name: str
    law_id: str | None
    from_mst: str
    to_mst: str
    from_effective_date: date | None
    to_effective_date: date | None
    article_stable_id: str
    article_no: str
    article_title: str | None
    change_type: str
    previous_content_hash: str | None
    current_content_hash: str | None
    affected_procedure_code: str | None
    affected_procedure_name: str | None
    candidate_id: int | None
    mapping_status: str
    previous_mapping_status: str | None
    derived_review_status: str
    impact_level: str
    impact_reason: str
    source_provenance: dict[str, Any]
    official_url: str | None
    official_url_status: str
    idempotency_key: str
    duplicate: bool = False

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass
class LawVersionImpactResult:
    status: str
    law_name: str
    law_id: str | None
    from_mst: str
    to_mst: str
    dry_run: bool
    diff_summary: dict[str, int]
    affected_articles: list[dict[str, Any]] = field(default_factory=list)
    affected_confirmed_mapping_count: int = 0
    affected_unconfirmed_candidate_count: int = 0
    stale_count: int = 0
    needs_revalidation_count: int = 0
    new_candidate_count: int = 0
    generated_event_count: int = 0
    skipped_duplicate_event_count: int = 0
    errors: list[str] = field(default_factory=list)
    secret_exposed: bool = False
    raw_payload_stored: bool = False

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


class LawVersionImpactService:
    def __init__(self, db: Session):
        self.db = db

    def analyze(self, law_name: str, from_mst: str, to_mst: str, dry_run: bool = True, force_rollback: bool = False) -> LawVersionImpactResult:
        diff = diff_moleg_versions(self.db, law_name=law_name, from_mst=from_mst, to_mst=to_mst)
        result = LawVersionImpactResult(
            status="ok" if diff.status == "ok" else diff.status,
            law_name=diff.law_name,
            law_id=diff.law_id,
            from_mst=from_mst,
            to_mst=to_mst,
            dry_run=dry_run,
            diff_summary={
                "added": len(diff.added),
                "removed": len(diff.removed),
                "changed": len(diff.changed),
                "unchanged": len(diff.unchanged),
            },
        )
        if diff.status != "ok":
            result.errors.append(diff.reason_type)
            return result
        from_doc = _find_document(self.db, law_name, from_mst)
        to_doc = _find_document(self.db, law_name, to_mst)
        if from_doc is None or to_doc is None:
            result.status = "missing_version"
            result.errors.append("version_not_available")
            return result
        if from_doc.law_id and to_doc.law_id and from_doc.law_id != to_doc.law_id:
            result.status = "law_id_mismatch"
            result.errors.append("from_to_law_id_mismatch")
            return result

        try:
            plans = self._build_plans(diff.changed, "changed", from_doc, to_doc)
            plans.extend(self._build_plans(diff.removed, "removed", from_doc, to_doc))
            plans.extend(self._build_added_plans(diff.added, from_doc, to_doc, dry_run=dry_run))
            for item in diff.unchanged:
                result.affected_articles.append({"article_no": item.article_no, "article_title": item.article_title, "change_type": "unchanged", "impact_level": IMPACT_INFORMATIONAL})

            for plan in plans:
                plan.duplicate = self._event_exists(plan.idempotency_key)
                result.affected_articles.append(plan.to_dict())
                if plan.mapping_status == STATUS_CONFIRMED:
                    result.affected_confirmed_mapping_count += 1
                if plan.mapping_status == STATUS_UNCONFIRMED:
                    result.affected_unconfirmed_candidate_count += 1
                if plan.derived_review_status == STATUS_NEEDS_REVALIDATION:
                    result.needs_revalidation_count += 1
                if plan.derived_review_status == STATUS_STALE:
                    result.stale_count += 1
                if plan.mapping_status == "new_unconfirmed_candidate":
                    result.new_candidate_count += 1
                if plan.duplicate:
                    result.skipped_duplicate_event_count += 1
                elif plan.change_type != "unchanged":
                    result.generated_event_count += 1
                    if not dry_run:
                        self.db.add(_event_from_plan(plan))
            if force_rollback:
                raise RuntimeError("PHASE40_TEST_ROLLBACK")
            if dry_run:
                self.db.rollback()
            else:
                self.db.commit()
        except Exception as exc:
            self.db.rollback()
            result.status = "rolled_back"
            result.errors.append(exc.__class__.__name__)
        return result

    def _build_plans(self, items: list[ArticleDiffItem], change_type: str, from_doc: OfficialLawDocument, to_doc: OfficialLawDocument) -> list[ImpactEventPlan]:
        plans: list[ImpactEventPlan] = []
        for item in items:
            before_article = self.db.get(OfficialLawArticleRecord, item.from_article_id) if item.from_article_id else None
            after_article = self.db.get(OfficialLawArticleRecord, item.to_article_id) if item.to_article_id else None
            candidates = _candidates_for_article(self.db, item.from_article_id)
            if not candidates:
                plans.append(self._plan(item, change_type, from_doc, to_doc, before_article, after_article, None, STATUS_UNMAPPED, STATUS_UNMAPPED, IMPACT_INFORMATIONAL, "연결된 절차 후보가 없는 조문 변경입니다."))
                continue
            for candidate in candidates:
                previous = _candidate_status(candidate)
                if previous == STATUS_REJECTED:
                    derived = STATUS_REJECTED
                    level = IMPACT_INFORMATIONAL
                    reason = "반려된 후보는 법령 개정으로 자동 부활하지 않습니다."
                elif candidate.is_confirmed and change_type == "changed":
                    derived = STATUS_NEEDS_REVALIDATION
                    level = IMPACT_HIGH
                    reason = "확정된 절차-조문 후보의 조문 내용이 변경되어 사람 검토가 필요합니다."
                elif candidate.is_confirmed and change_type == "removed":
                    derived = STATUS_STALE
                    level = IMPACT_HIGH
                    reason = "확정된 절차-조문 후보의 조문이 새 버전에서 삭제되어 확정 근거로 표시하지 않습니다."
                elif change_type == "removed":
                    derived = STATUS_STALE
                    level = IMPACT_MEDIUM
                    reason = "미확정 후보의 조문이 새 버전에서 삭제되어 검토 문맥이 사라졌습니다."
                else:
                    derived = STATUS_UNCONFIRMED
                    level = IMPACT_MEDIUM
                    reason = "미확정 후보의 조문 내용이 변경되어 검토 문맥이 변경되었습니다."
                plans.append(self._plan(item, change_type, from_doc, to_doc, before_article, after_article, candidate, previous, derived, level, reason))
        return plans

    def _build_added_plans(self, items: list[ArticleDiffItem], from_doc: OfficialLawDocument, to_doc: OfficialLawDocument, dry_run: bool) -> list[ImpactEventPlan]:
        if not items:
            return []
        before_ids = set(self.db.scalars(select(ProcedureOfficialArticleCandidate.id).where(ProcedureOfficialArticleCandidate.law_id == to_doc.law_id)).all())
        added_article_ids = {item.to_article_id for item in items if item.to_article_id is not None}
        if dry_run:
            preview = resolve_procedure_article_candidates(db=self.db, law_title=to_doc.law_title, source_mode_detail="official_db", include_unmatched=False, persist=False)
            new_candidates = [
                ProcedureArticleCandidate.model_validate(candidate)
                for group in preview["items"]
                for candidate in group["candidates"]
                if candidate.get("article_id") in added_article_ids
            ]
        else:
            resolve_procedure_article_candidates(db=self.db, law_title=to_doc.law_title, source_mode_detail="official_db", include_unmatched=False, persist=True)
            after_rows = list(self.db.scalars(select(ProcedureOfficialArticleCandidate).where(ProcedureOfficialArticleCandidate.law_id == to_doc.law_id)).all())
            new_candidates = [row for row in after_rows if row.article_id in added_article_ids and row.id not in before_ids]
        plans: list[ImpactEventPlan] = []
        for item in items:
            after_article = self.db.get(OfficialLawArticleRecord, item.to_article_id) if item.to_article_id else None
            matched = [row for row in new_candidates if row.article_id == item.to_article_id]
            if not matched and dry_run and after_article is not None:
                matched = _preview_added_candidates(to_doc, after_article)
            if not matched:
                plans.append(self._plan(item, "added", from_doc, to_doc, None, after_article, None, STATUS_UNMAPPED, STATUS_UNMAPPED, IMPACT_INFORMATIONAL, "신규 조문이지만 연결된 절차 후보가 없습니다."))
                continue
            for candidate in matched:
                plans.append(self._plan(item, "added", from_doc, to_doc, None, after_article, candidate, "new_unconfirmed_candidate", STATUS_UNCONFIRMED, IMPACT_MEDIUM, "신규 조문으로 미확정 절차 후보가 생성되었습니다."))
        return plans
    def _plan(self, item: ArticleDiffItem, change_type: str, from_doc: OfficialLawDocument, to_doc: OfficialLawDocument, before_article: OfficialLawArticleRecord | None, after_article: OfficialLawArticleRecord | None, candidate: ProcedureOfficialArticleCandidate | None, mapping_status: str, derived: str, level: str, reason: str) -> ImpactEventPlan:
        article = after_article or before_article
        article_no = item.article_no
        article_title = item.article_title
        stable_id = _stable_article_id(to_doc.law_id or from_doc.law_id, article)
        candidate_part = "none" if candidate is None else str(candidate.id)
        key = "|".join([to_doc.law_id or from_doc.law_id or "", from_doc.mst or "", to_doc.mst or "", stable_id, candidate_part, change_type])
        official_url = to_doc.sanitized_source_url or from_doc.sanitized_source_url or None
        return ImpactEventPlan(
            law_name=to_doc.law_title,
            law_id=to_doc.law_id or from_doc.law_id,
            from_mst=from_doc.mst or "",
            to_mst=to_doc.mst or "",
            from_effective_date=from_doc.enforcement_date,
            to_effective_date=to_doc.enforcement_date,
            article_stable_id=stable_id,
            article_no=article_no,
            article_title=article_title,
            change_type=change_type,
            previous_content_hash=_content_hash(before_article),
            current_content_hash=_content_hash(after_article),
            affected_procedure_code=None if candidate is None else candidate.procedure_code,
            affected_procedure_name=None if candidate is None else candidate.procedure_name,
            candidate_id=None if candidate is None else candidate.id,
            mapping_status=mapping_status,
            previous_mapping_status=mapping_status,
            derived_review_status=derived,
            impact_level=level,
            impact_reason=reason,
            source_provenance={"source_provider": to_doc.source_provider, "source_mode": to_doc.source_mode, "from_document_id": from_doc.id, "to_document_id": to_doc.id, "legal_interpretation": False},
            official_url=official_url,
            official_url_status="available" if official_url else "unavailable",
            idempotency_key=hashlib.sha256(key.encode("utf-8")).hexdigest(),
        )

    def _event_exists(self, idempotency_key: str) -> bool:
        return self.db.scalar(select(LawChangeImpactEvent.id).where(LawChangeImpactEvent.idempotency_key == idempotency_key).limit(1)) is not None


def list_law_change_impact_events(db: Session, status: str | None = None) -> list[LawChangeImpactEvent]:
    statement = select(LawChangeImpactEvent).order_by(LawChangeImpactEvent.detected_at.desc(), LawChangeImpactEvent.id.desc())
    if status:
        statement = statement.where(LawChangeImpactEvent.derived_review_status == status)
    return list(db.scalars(statement).all())


def _event_from_plan(plan: ImpactEventPlan) -> LawChangeImpactEvent:
    return LawChangeImpactEvent(
        idempotency_key=plan.idempotency_key,
        law_name=plan.law_name,
        law_id=plan.law_id,
        from_mst=plan.from_mst,
        to_mst=plan.to_mst,
        from_effective_date=plan.from_effective_date,
        to_effective_date=plan.to_effective_date,
        article_stable_id=plan.article_stable_id,
        article_no=plan.article_no,
        article_title=plan.article_title,
        change_type=plan.change_type,
        previous_content_hash=plan.previous_content_hash,
        current_content_hash=plan.current_content_hash,
        affected_procedure_code=plan.affected_procedure_code,
        affected_procedure_name=plan.affected_procedure_name,
        candidate_id=plan.candidate_id,
        mapping_status=plan.mapping_status,
        previous_mapping_status=plan.previous_mapping_status,
        derived_review_status=plan.derived_review_status,
        impact_level=plan.impact_level,
        impact_reason=plan.impact_reason,
        source_provenance=plan.source_provenance,
        official_url=plan.official_url,
        official_url_status=plan.official_url_status,
        processed_at=datetime.now(UTC),
        metadata_json={"raw_payload_stored": False, "secret_exposed": False, "legal_interpretation": False},
    )


def _find_document(db: Session, law_name: str, mst: str) -> OfficialLawDocument | None:
    return db.scalar(select(OfficialLawDocument).where(OfficialLawDocument.source_provider == "moleg_open_api", OfficialLawDocument.source_mode == "live", OfficialLawDocument.law_title == law_name, OfficialLawDocument.mst == mst))


def _candidates_for_article(db: Session, article_id: int | None) -> list[ProcedureOfficialArticleCandidate]:
    if article_id is None:
        return []
    return list(db.scalars(select(ProcedureOfficialArticleCandidate).where(ProcedureOfficialArticleCandidate.article_id == article_id).order_by(ProcedureOfficialArticleCandidate.id)).all())


def _candidate_status(candidate: ProcedureOfficialArticleCandidate) -> str:
    if candidate.confirmed_source == REVIEW_SOURCE_REJECTED:
        return STATUS_REJECTED
    if candidate.is_confirmed:
        return STATUS_CONFIRMED
    return STATUS_UNCONFIRMED


def _stable_article_id(law_id: str | None, article: OfficialLawArticleRecord | None) -> str:
    if article is None:
        return f"{law_id or 'unknown'}|unknown"
    if article.source_anchor:
        return f"{law_id or 'unknown'}|{article.article_no}|{article.source_anchor}"
    return f"{law_id or 'unknown'}|{article.article_no}"


def _content_hash(article: OfficialLawArticleRecord | None) -> str | None:
    if article is None:
        return None
    normalized = "\n".join([" ".join((article.article_title or "").split()).casefold(), " ".join((article.article_text or "").split()).casefold()])
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()




def _preview_added_candidates(document: OfficialLawDocument, article: OfficialLawArticleRecord) -> list[ProcedureArticleCandidate]:
    data = load_yaml_rule("procedure_article_keywords.yaml")
    title_blob = " ".join((article.article_title or "").split()).casefold()
    text_blob = " ".join((article.article_text or "").split()).casefold()
    results: list[ProcedureArticleCandidate] = []
    for config in data.get("steps", []):
        if not isinstance(config, dict) or not config.get("procedure_code"):
            continue
        preferred = [" ".join(str(value).split()).casefold() for value in config.get("preferred_laws", [])]
        if preferred and " ".join(document.law_title.split()).casefold() not in preferred:
            continue
        keywords = [" ".join(str(value).split()).casefold() for value in config.get("keywords", []) if str(value).strip()]
        if not any(keyword and (keyword in title_blob or keyword in text_blob) for keyword in keywords):
            continue
        results.append(
            ProcedureArticleCandidate(
                procedure_code=config["procedure_code"],
                procedure_name=config.get("procedure_name"),
                article_id=article.id,
                document_id=document.id,
                law_title=document.law_title,
                law_short_title=document.law_short_title,
                law_id=document.law_id,
                mst=document.mst,
                article_no=article.article_no,
                article_title=article.article_title,
                article_anchor=article.source_anchor,
                match_method="title_or_text_keyword_preview",
                match_score=60,
                match_status="candidate",
                confidence_level="medium",
                source_mode="official_db",
                source_mode_detail="official_db",
                is_confirmed=False,
            )
        )
    return results
