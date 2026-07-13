from __future__ import annotations

from datetime import UTC, date, datetime
import json

from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select

from app.core.database import SessionLocal
from app.main import app
from app.models import OfficialLawArticleRecord, OfficialLawDocument, ProcedureOfficialArticleCandidate
from app.services.procedure_article_candidate_service import resolve_procedure_article_candidates
from app.services.procedure_article_review_service import (
    REVIEW_SOURCE_CONFIRMED,
    REVIEW_SOURCE_REJECTED,
    candidate_detail,
    confirm_candidate,
    list_review_candidates,
    reject_candidate,
    reopen_candidate,
)

client = TestClient(app)
LAW_ID = "PHASE39-LAW-ID"
MST = "PHASE39-MST-CURRENT"
OLD_MST = "PHASE39-MST-OLD"
ARTICLE_NO = "PHASE39-ARTICLE"
PROCEDURE_CODE = "PROJECT_BASIC_REVIEW"


def _cleanup():
    db = SessionLocal()
    try:
        rows = db.scalars(select(ProcedureOfficialArticleCandidate).where(ProcedureOfficialArticleCandidate.law_id == LAW_ID)).all()
        for row in rows:
            db.delete(row)
        db.flush()
        doc_ids = list(db.scalars(select(OfficialLawDocument.id).where(OfficialLawDocument.law_id == LAW_ID)).all())
        if doc_ids:
            db.execute(delete(OfficialLawArticleRecord).where(OfficialLawArticleRecord.document_id.in_(doc_ids)))
            db.execute(delete(OfficialLawDocument).where(OfficialLawDocument.id.in_(doc_ids)))
        db.commit()
    finally:
        db.close()


def _make_candidate(mst: str = MST, source_url: str = "") -> int:
    db = SessionLocal()
    try:
        doc = OfficialLawDocument(
            source_provider="moleg_open_api",
            source_mode="live",
            law_title="Phase39 Dummy Law",
            law_short_title=None,
            law_id=LAW_ID,
            mst=mst,
            promulgation_date=date(2098, 1, 1),
            enforcement_date=date(2099, 1, 1) if mst == MST else date(2098, 1, 1),
            is_current=True,
            document_status="normalized",
            normalized_at=datetime.now(UTC),
            provider_reason="Phase39 fixture only.",
            sanitized_source_url=source_url,
        )
        db.add(doc)
        db.flush()
        article = OfficialLawArticleRecord(
            document_id=doc.id,
            article_no=ARTICLE_NO,
            article_title="Phase39 Dummy Article",
            article_text="Phase39 fixture article body only. It is not legal advice.",
            paragraphs_json=["Phase39 fixture paragraph."],
            source_anchor=None,
            source_hint="Phase39 fixture source hint.",
            sort_order=1,
        )
        db.add(article)
        db.flush()
        candidate = ProcedureOfficialArticleCandidate(
            procedure_code=PROCEDURE_CODE,
            procedure_name="Project basic review",
            law_title=doc.law_title,
            law_short_title=doc.law_short_title,
            law_id=doc.law_id,
            mst=doc.mst,
            document_id=doc.id,
            article_id=article.id,
            article_no=article.article_no,
            article_title=article.article_title,
            article_anchor=article.source_anchor,
            match_method="phase39_fixture",
            match_score=99,
            match_status="candidate",
            source_mode="official_db",
            source_mode_detail="official_db",
            confidence_level="high",
            is_confirmed=False,
            provider_reason="Phase39 fixture candidate only.",
        )
        db.add(candidate)
        db.commit()
        return candidate.id
    finally:
        db.close()


def test_phase39_list_show_and_validation():
    _cleanup()
    try:
        candidate_id = _make_candidate()
        db = SessionLocal()
        try:
            items = list_review_candidates(db, status="unconfirmed")
            assert any(item["candidate_id"] == candidate_id for item in items)
            detail = candidate_detail(db, candidate_id)
            assert detail["candidate_status"] == "unconfirmed"
            assert detail["official_url"] is None
            assert detail["official_url_status"] == "unavailable"
            assert detail["article_text"]
            assert confirm_candidate(db, candidate_id, None, "note").status == "validation_error"
            assert confirm_candidate(db, candidate_id, "reviewer", None).status == "validation_error"
            assert confirm_candidate(db, 999999999, "reviewer", "note").status == "not_found"
        finally:
            db.close()
    finally:
        _cleanup()


def test_phase39_confirm_reject_reopen_and_rollback():
    _cleanup()
    try:
        candidate_id = _make_candidate(source_url="https://example.invalid/official")
        db = SessionLocal()
        try:
            rollback = confirm_candidate(db, candidate_id, "tester", "rollback note", force_rollback=True)
            assert rollback.status == "rolled_back"
            assert candidate_detail(db, candidate_id)["candidate_status"] == "unconfirmed"
            confirmed = confirm_candidate(db, candidate_id, "tester", "confirmed note")
            assert confirmed.status == "ok"
            detail = candidate_detail(db, candidate_id)
            assert detail["candidate_status"] == "confirmed"
            assert detail["confirmed_under_mst"] == MST
            assert detail["official_url_status"] == "available"
            rejected = reject_candidate(db, candidate_id, "tester", "rejected note")
            assert rejected.status == "ok"
            assert candidate_detail(db, candidate_id)["candidate_status"] == "rejected"
            reopened = reopen_candidate(db, candidate_id, "tester", "reopen note")
            assert reopened.status == "ok"
            assert candidate_detail(db, candidate_id)["candidate_status"] == "unconfirmed"
        finally:
            db.close()
    finally:
        _cleanup()


def test_phase39_candidate_refresh_preserves_review_states_and_prevents_duplicates():
    _cleanup()
    try:
        candidate_id = _make_candidate()
        db = SessionLocal()
        try:
            assert confirm_candidate(db, candidate_id, "tester", "confirmed note").status == "ok"
            before = db.scalar(select(func.count()).select_from(ProcedureOfficialArticleCandidate).where(ProcedureOfficialArticleCandidate.law_id == LAW_ID))
            resolve_procedure_article_candidates(db=db, procedure_code=PROCEDURE_CODE, law_title="Phase39 Dummy Law", source_mode_detail="official_db", include_unmatched=True, persist=True)
            after = db.scalar(select(func.count()).select_from(ProcedureOfficialArticleCandidate).where(ProcedureOfficialArticleCandidate.law_id == LAW_ID))
            row = db.get(ProcedureOfficialArticleCandidate, candidate_id)
            assert before == after
            assert row.is_confirmed is True
            assert row.confirmed_source == REVIEW_SOURCE_CONFIRMED
            assert reject_candidate(db, candidate_id, "tester", "reject note").status == "ok"
            resolve_procedure_article_candidates(db=db, procedure_code=PROCEDURE_CODE, law_title="Phase39 Dummy Law", source_mode_detail="official_db", include_unmatched=True, persist=True)
            row = db.get(ProcedureOfficialArticleCandidate, candidate_id)
            assert row.is_confirmed is False
            assert row.confirmed_source == REVIEW_SOURCE_REJECTED
        finally:
            db.close()
    finally:
        _cleanup()


def test_phase39_analyze_uses_only_confirmed_candidates_and_excludes_rejected():
    _cleanup()
    try:
        candidate_id = _make_candidate()
        payload = {"project_name":"Phase39","location":"Test","area_square_meters":100000,"implementation_method":"expropriation_or_use","implementer_type":"public","local_government":"Test"}
        unconfirmed = client.post("/api/analyze", json=payload).json()
        target = next(step for step in unconfirmed["procedures"] if step["step_code"] == PROCEDURE_CODE)
        assert all(ref.get("notes", {}).get("candidate_id") != candidate_id for ref in target["legal_references"])
        db = SessionLocal()
        try:
            assert confirm_candidate(db, candidate_id, "tester", "confirmed for fixture").status == "ok"
        finally:
            db.close()
        confirmed = client.post("/api/analyze", json=payload).json()
        target = next(step for step in confirmed["procedures"] if step["step_code"] == PROCEDURE_CODE)
        assert any(ref.get("notes", {}).get("candidate_id") == candidate_id for ref in target["legal_references"])
        db = SessionLocal()
        try:
            assert reject_candidate(db, candidate_id, "tester", "reject after confirm").status == "ok"
        finally:
            db.close()
        rejected = client.post("/api/analyze", json=payload).json()
        target = next(step for step in rejected["procedures"] if step["step_code"] == PROCEDURE_CODE)
        assert all(ref.get("notes", {}).get("candidate_id") != candidate_id for ref in target["legal_references"])
    finally:
        _cleanup()


def test_phase39_needs_revalidation_and_secret_policy():
    _cleanup()
    try:
        candidate_id = _make_candidate(mst=OLD_MST)
        _make_candidate(mst=MST)
        db = SessionLocal()
        try:
            assert confirm_candidate(db, candidate_id, "tester", "confirmed old mst").status == "ok"
            detail = candidate_detail(db, candidate_id)
            assert detail["candidate_status"] == "needs_revalidation"
            dumped = json.dumps(detail, ensure_ascii=False)
            assert "TEST_PHASE" not in dumped
            assert detail["raw_payload_stored"] is False
            assert detail["secret_exposed"] is False
        finally:
            db.close()
    finally:
        _cleanup()
