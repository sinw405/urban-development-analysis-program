from __future__ import annotations

from datetime import UTC, date, datetime

from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select

from app.core.database import SessionLocal
from app.main import app
from app.models import LawChangeImpactEvent, OfficialLawArticleRecord, OfficialLawDocument, ProcedureArticleReviewEvent, ProcedureOfficialArticleCandidate
from app.services.law_version_impact_service import LawVersionImpactService
from app.services.procedure_article_review_service import confirm_candidate, reject_candidate, reopen_candidate

client = TestClient(app)
LAW_NAME = "도시개발법"
LAW_ID = "PHASE40_TEST_LAW_ID_DO_NOT_USE"
FROM_MST = "PHASE40_FROM_MST_DO_NOT_USE"
TO_MST = "PHASE40_TO_MST_DO_NOT_USE"
PROC = "PROJECT_BASIC_REVIEW"


def _cleanup():
    db = SessionLocal()
    try:
        candidate_ids = list(db.scalars(select(ProcedureOfficialArticleCandidate.id).where(ProcedureOfficialArticleCandidate.law_id == LAW_ID)).all())
        if candidate_ids:
            db.execute(delete(LawChangeImpactEvent).where(LawChangeImpactEvent.candidate_id.in_(candidate_ids)))
            db.execute(delete(ProcedureArticleReviewEvent).where(ProcedureArticleReviewEvent.candidate_id.in_(candidate_ids)))
            db.execute(delete(ProcedureOfficialArticleCandidate).where(ProcedureOfficialArticleCandidate.id.in_(candidate_ids)))
        db.execute(delete(LawChangeImpactEvent).where(LawChangeImpactEvent.law_id == LAW_ID))
        doc_ids = list(db.scalars(select(OfficialLawDocument.id).where(OfficialLawDocument.law_id == LAW_ID)).all())
        if doc_ids:
            db.execute(delete(OfficialLawArticleRecord).where(OfficialLawArticleRecord.document_id.in_(doc_ids)))
            db.execute(delete(OfficialLawDocument).where(OfficialLawDocument.id.in_(doc_ids)))
        db.commit()
    finally:
        db.close()


def _doc(db, mst: str, eff: date) -> OfficialLawDocument:
    row = OfficialLawDocument(
        source_provider="moleg_open_api",
        source_mode="live",
        law_title=LAW_NAME,
        law_short_title=None,
        law_id=LAW_ID,
        mst=mst,
        promulgation_date=eff,
        enforcement_date=eff,
        is_current=True,
        document_status="normalized",
        normalized_at=datetime.now(UTC),
        provider_reason="PHASE40 fixture only.",
        sanitized_source_url="https://example.invalid/moleg/phase40",
    )
    db.add(row)
    db.flush()
    return row


def _article(db, doc: OfficialLawDocument, no: str, title: str, text: str, order: int) -> OfficialLawArticleRecord:
    row = OfficialLawArticleRecord(
        document_id=doc.id,
        article_no=no,
        article_title=title,
        article_text=text,
        paragraphs_json=[text],
        source_anchor=None,
        source_hint="PHASE40 fixture only.",
        sort_order=order,
    )
    db.add(row)
    db.flush()
    return row


def _candidate(db, article: OfficialLawArticleRecord, confirmed: bool = False, rejected: bool = False) -> int:
    row = ProcedureOfficialArticleCandidate(
        procedure_code=PROC,
        procedure_name="Project basic review",
        law_title=LAW_NAME,
        law_short_title=None,
        law_id=LAW_ID,
        mst=FROM_MST,
        document_id=article.document_id,
        article_id=article.id,
        article_no=article.article_no,
        article_title=article.article_title,
        article_anchor=article.source_anchor,
        match_method="phase40_fixture",
        match_score=99,
        match_status="candidate",
        source_mode="official_db",
        source_mode_detail="official_db",
        confidence_level="high",
        is_confirmed=False,
        provider_reason="PHASE40 fixture candidate only.",
    )
    db.add(row)
    db.flush()
    cid = row.id
    db.commit()
    if confirmed:
        assert confirm_candidate(db, cid, "phase40_tester", "confirm fixture").status == "ok"
    if rejected:
        assert reject_candidate(db, cid, "phase40_tester", "reject fixture").status == "ok"
    return cid


def _fixture(changed=True, removed=False, added=False, unchanged=False, candidate_status="confirmed") -> int | None:
    db = SessionLocal()
    try:
        before = _doc(db, FROM_MST, date(2098, 1, 1))
        after = _doc(db, TO_MST, date(2099, 1, 1))
        before_article = None
        if changed:
            before_article = _article(db, before, "제1조", "기본 사업", "old body", 1)
            _article(db, after, "제1조", "기본 사업", "new body", 1)
        if removed:
            before_article = _article(db, before, "제2조", "삭제 사업", "removed body", 2)
        if added:
            _article(db, after, "제3조", "기본 신규 사업", "added body", 3)
        if unchanged:
            before_article = _article(db, before, "제4조", "기본 유지", "same body", 4)
            _article(db, after, "제4조", "기본 유지", "same body", 4)
        db.commit()
        if before_article is None:
            return None
        if candidate_status == "none":
            return None
        return _candidate(db, before_article, confirmed=candidate_status == "confirmed", rejected=candidate_status == "rejected")
    finally:
        db.close()


def test_confirmed_changed_creates_needs_revalidation_event_and_analyze_excludes_basis():
    _cleanup()
    try:
        cid = _fixture(changed=True, candidate_status="confirmed")
        db = SessionLocal()
        try:
            result = LawVersionImpactService(db).analyze(LAW_NAME, FROM_MST, TO_MST, dry_run=False)
            assert result.status == "ok"
            assert result.needs_revalidation_count == 1
            assert result.generated_event_count == 1
        finally:
            db.close()
        response = client.post("/api/analyze", json={"project_name":"p40","location":"x","area_square_meters":100000,"implementation_method":"mixed","implementer_type":"public","local_government":"x"})
        target = next(step for step in response.json()["procedures"] if step["step_code"] == PROC)
        assert target["reference_status"] == "needs_revalidation"
        assert all(ref.get("notes", {}).get("candidate_id") != cid for ref in target["legal_references"])
    finally:
        _cleanup()


def test_confirmed_removed_creates_stale_event_and_duplicate_apply_skips():
    _cleanup()
    try:
        _fixture(changed=False, removed=True, candidate_status="confirmed")
        db = SessionLocal()
        try:
            first = LawVersionImpactService(db).analyze(LAW_NAME, FROM_MST, TO_MST, dry_run=False)
            second = LawVersionImpactService(db).analyze(LAW_NAME, FROM_MST, TO_MST, dry_run=False)
            assert first.stale_count == 1
            assert first.generated_event_count == 1
            assert second.generated_event_count == 0
            assert second.skipped_duplicate_event_count == 1
            assert db.scalar(select(func.count()).select_from(LawChangeImpactEvent).where(LawChangeImpactEvent.law_id == LAW_ID)) == 1
        finally:
            db.close()
    finally:
        _cleanup()


def test_dry_run_keeps_db_counts_and_added_candidate_is_unconfirmed_preview():
    _cleanup()
    try:
        _fixture(changed=False, added=True, candidate_status="none")
        db = SessionLocal()
        try:
            before_candidates = db.scalar(select(func.count()).select_from(ProcedureOfficialArticleCandidate).where(ProcedureOfficialArticleCandidate.law_id == LAW_ID))
            before_events = db.scalar(select(func.count()).select_from(LawChangeImpactEvent).where(LawChangeImpactEvent.law_id == LAW_ID))
            result = LawVersionImpactService(db).analyze(LAW_NAME, FROM_MST, TO_MST, dry_run=True)
            after_candidates = db.scalar(select(func.count()).select_from(ProcedureOfficialArticleCandidate).where(ProcedureOfficialArticleCandidate.law_id == LAW_ID))
            after_events = db.scalar(select(func.count()).select_from(LawChangeImpactEvent).where(LawChangeImpactEvent.law_id == LAW_ID))
            assert result.new_candidate_count >= 1
            assert result.generated_event_count >= 1
            assert before_candidates == after_candidates
            assert before_events == after_events
        finally:
            db.close()
    finally:
        _cleanup()


def test_unconfirmed_and_rejected_are_not_auto_confirmed_and_review_history_preserved():
    _cleanup()
    try:
        cid = _fixture(changed=True, candidate_status="rejected")
        db = SessionLocal()
        try:
            result = LawVersionImpactService(db).analyze(LAW_NAME, FROM_MST, TO_MST, dry_run=False)
            row = db.get(ProcedureOfficialArticleCandidate, cid)
            assert result.status == "ok"
            assert row.is_confirmed is False
            assert row.confirmed_source == "manual_review_rejected"
            assert reopen_candidate(db, cid, "phase40_tester", "reopen fixture").status == "ok"
            assert db.scalar(select(func.count()).select_from(ProcedureArticleReviewEvent).where(ProcedureArticleReviewEvent.candidate_id == cid)) == 2
        finally:
            db.close()
    finally:
        _cleanup()


def test_law_updates_api_lists_impact_events_and_same_mst_is_unchanged():
    _cleanup()
    try:
        _fixture(changed=True, unchanged=True, candidate_status="confirmed")
        db = SessionLocal()
        try:
            same = LawVersionImpactService(db).analyze(LAW_NAME, FROM_MST, FROM_MST, dry_run=True)
            assert same.diff_summary["changed"] == 0
            LawVersionImpactService(db).analyze(LAW_NAME, FROM_MST, TO_MST, dry_run=False)
        finally:
            db.close()
        response = client.get("/api/law-updates")
        assert response.status_code == 200
        assert any(item["event_kind"] == "law_change_impact" and item["law_id"] == LAW_ID for item in response.json()["items"])
        alias = client.get("/api/updates")
        assert alias.status_code == 200
    finally:
        _cleanup()
