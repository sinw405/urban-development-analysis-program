from datetime import date
from sqlalchemy import delete, func, select
from app.core.database import SessionLocal
from app.models import LiveLawChangeEvent, LiveLawChangeEventAudit, OfficialLawArticleRecord, OfficialLawDocument
from app.services.live_law_change_persistence_service import build_idempotency_key, execute_phase43, get_version_by_mst, has_version_document
from app.services.moleg_version_discovery_service import LawVersionDescriptor, LawVersionPairSelection

LAW = "TEST_PHASE43_LAW_DO_NOT_USE"
LAW_ID = "P43LAW"
FROM = "P43001"
TO = "P43002"

def _cleanup():
    with SessionLocal() as db:
        ids = list(db.scalars(select(OfficialLawDocument.id).where(OfficialLawDocument.law_title == LAW)).all())
        event_ids = list(db.scalars(select(LiveLawChangeEvent.id).where(LiveLawChangeEvent.law_name == LAW)).all())
        if event_ids: db.execute(delete(LiveLawChangeEventAudit).where(LiveLawChangeEventAudit.event_id.in_(event_ids)))
        db.execute(delete(LiveLawChangeEvent).where(LiveLawChangeEvent.law_name == LAW))
        if ids: db.execute(delete(OfficialLawArticleRecord).where(OfficialLawArticleRecord.document_id.in_(ids)))
        db.execute(delete(OfficialLawDocument).where(OfficialLawDocument.law_title == LAW))
        db.commit()

def _doc(db, mst, eff, articles, status="normalized"):
    doc=OfficialLawDocument(source_provider="moleg_open_api", source_mode="live", law_title=LAW, law_id=LAW_ID, mst=mst,
        promulgation_date=eff, enforcement_date=eff, is_current=mst==TO, document_status=status,
        normalized_at=date.today(), sanitized_source_url="https://example.invalid/DRF/lawService.do?OC=%5BREDACTED%5D")
    db.add(doc); db.flush()
    for order,(no,title,text) in enumerate(articles,1):
        db.add(OfficialLawArticleRecord(document_id=doc.id, article_no=no, article_title=title, article_text=text, sort_order=order))
    db.commit(); return doc

def _selection():
    a=LawVersionDescriptor(LAW_ID,LAW,FROM,date(2025,1,1),date(2025,1,1),None,None,"history")
    b=LawVersionDescriptor(LAW_ID,LAW,TO,date(2026,1,1),date(2026,1,1),None,None,"current")
    return LawVersionPairSelection(LAW,a,b,"test")

def test_phase43_complete_document_state_and_metadata_only_is_incomplete():
    _cleanup()
    with SessionLocal() as db:
        _doc(db,FROM,date(2025,1,1),[("1","title","body")])
        _doc(db,TO,date(2026,1,1),[],status="partial")
        assert has_version_document(db,FROM,LAW)
        state=get_version_by_mst(db,TO,LAW)
        assert state.document_id and state.article_count==0 and not state.complete
    _cleanup()

def test_phase43_idempotency_key_is_deterministic_and_pair_specific():
    one=build_idempotency_key("MOLEG",LAW_ID,FROM,TO)
    assert one==build_idempotency_key("moleg",LAW_ID.lower(),FROM,TO)
    assert one!=build_idempotency_key("MOLEG",LAW_ID,TO,FROM)
    assert len(one)==64

def test_phase43_added_removed_modified_and_counts_are_persisted():
    _cleanup()
    with SessionLocal() as db:
        _doc(db,FROM,date(2025,1,1),[("1","same","old"),("2","removed","gone"),("4","unchanged","same")])
        _doc(db,TO,date(2026,1,1),[("1","same","new"),("3","added","here"),("4","unchanged","same")])
        result=execute_phase43(db,object(),_selection(),ensure_versions=False,persist_event=True)
        assert result.status=="ok" and result.analysis_status=="completed"
        assert result.version_changed and result.content_changed
        assert sorted(x["change_type"] for x in result.changed_articles)==["added","modified","removed"]
        assert result.event.changed_article_count==3
        assert result.event.idempotency_key==build_idempotency_key("MOLEG",LAW_ID,FROM,TO)
    _cleanup()

def test_phase43_whitespace_only_is_no_change():
    _cleanup()
    with SessionLocal() as db:
        _doc(db,FROM,date(2025,1,1),[("1","title","alpha   beta\n gamma")])
        _doc(db,TO,date(2026,1,1),[("1","title","alpha beta gamma")])
        result=execute_phase43(db,object(),_selection(),ensure_versions=False,persist_event=True)
        assert result.status=="ok" and result.analysis_status=="no_change"
        assert result.version_changed and result.content_changed is False and result.changed_articles==[]
    _cleanup()

def test_phase43_same_request_reuses_one_event_and_appends_audit():
    _cleanup()
    with SessionLocal() as db:
        _doc(db,FROM,date(2025,1,1),[("1","title","old")]); _doc(db,TO,date(2026,1,1),[("1","title","new")])
        first=execute_phase43(db,object(),_selection(),ensure_versions=False,persist_event=True)
        second=execute_phase43(db,object(),_selection(),ensure_versions=False,persist_event=True)
        assert first.event.id==second.event.id and first.event_created and not second.event_created
        assert db.scalar(select(func.count()).select_from(LiveLawChangeEvent).where(LiveLawChangeEvent.law_name==LAW))==1
        actions=list(db.scalars(select(LiveLawChangeEventAudit.action).where(LiveLawChangeEventAudit.event_id==first.event.id).order_by(LiveLawChangeEventAudit.id)).all())
        assert actions[:3]==["discovered","ingest_started","ingest_completed"] or actions[:2]==["discovered","analysis_started"]
        assert actions[-1]=="persisted"
    _cleanup()

def test_phase43_missing_version_has_explicit_status_and_failure_audit():
    _cleanup()
    with SessionLocal() as db:
        result=execute_phase43(db,object(),_selection(),ensure_versions=False,persist_event=True)
        assert result.status=="missing_version" and result.content_changed is None
        assert result.errors==["version_not_available"]
        assert result.event.analysis_status=="missing_version"
    _cleanup()

def test_phase43_event_json_never_contains_secret_or_full_url():
    _cleanup()
    with SessionLocal() as db:
        _doc(db,FROM,date(2025,1,1),[("1","title","old")]); _doc(db,TO,date(2026,1,1),[("1","title","new")])
        result=execute_phase43(db,object(),_selection(),ensure_versions=False,persist_event=True)
        payload=str(result.event.changed_articles_json)+str(result.event.impacted_rules_json)
        assert "OC=" not in payload and "API_KEY" not in payload
    _cleanup()

import pytest
from types import SimpleNamespace
from app.services.live_law_change_persistence_service import ensure_version_documents

@pytest.mark.parametrize("existing,expected", [
    ((FROM,TO), []), ((FROM,), [TO]), ((TO,), [FROM]), ((), [FROM,TO]),
])
def test_phase43_ensure_fetches_only_incomplete_versions(monkeypatch, existing, expected):
    _cleanup()
    with SessionLocal() as db:
        for mst in existing:
            _doc(db,mst,date(2025,1,1) if mst==FROM else date(2026,1,1),[("1","title",mst)])
        calls=[]
        def fake_ingest(db, client, descriptors, dry_run=False):
            calls.extend(item.mst for item in descriptors)
            for item in descriptors:
                _doc(db,item.mst,item.enforcement_date,[("1","title",item.mst)])
            return SimpleNamespace(status="completed", errors=[])
        monkeypatch.setattr("app.services.moleg_version_discovery_service.ingest_law_versions",fake_ingest)
        states,ingested,errors=ensure_version_documents(db,object(),_selection())
        assert calls==expected and ingested==expected and errors==[] and all(x.complete for x in states)
    _cleanup()

def test_phase43_metadata_only_document_is_refetched(monkeypatch):
    _cleanup()
    with SessionLocal() as db:
        _doc(db,FROM,date(2025,1,1),[],status="partial"); _doc(db,TO,date(2026,1,1),[("1","title","new")])
        calls=[]
        def fake(db,client,descriptors,dry_run=False):
            calls.extend(x.mst for x in descriptors)
            old=db.scalar(select(OfficialLawDocument).where(OfficialLawDocument.mst==FROM)); old.document_status="normalized"
            db.add(OfficialLawArticleRecord(document_id=old.id,article_no="1",article_title="title",article_text="old",sort_order=1)); db.commit()
            return SimpleNamespace(status="completed",errors=[])
        monkeypatch.setattr("app.services.moleg_version_discovery_service.ingest_law_versions",fake)
        states,_,errors=ensure_version_documents(db,object(),_selection())
        assert calls==[FROM] and not errors and states[0].complete
    _cleanup()

def test_phase43_ingest_failure_is_not_mocked_as_success(monkeypatch):
    _cleanup()
    with SessionLocal() as db:
        monkeypatch.setattr("app.services.moleg_version_discovery_service.ingest_law_versions",lambda *a,**k: SimpleNamespace(status="source_error",errors=["api_error_response"]))
        result=execute_phase43(db,object(),_selection(),ensure_versions=True,persist_event=True)
        assert result.analysis_status=="ingest_failed" and result.content_changed is None
        assert "api_error_response" in result.errors
    _cleanup()

def test_phase43_empty_article_ingest_remains_incomplete(monkeypatch):
    _cleanup()
    with SessionLocal() as db:
        def fake(db,client,descriptors,dry_run=False):
            for item in descriptors: _doc(db,item.mst,item.enforcement_date,[],status="partial")
            return SimpleNamespace(status="completed",errors=[])
        monkeypatch.setattr("app.services.moleg_version_discovery_service.ingest_law_versions",fake)
        result=execute_phase43(db,object(),_selection(),ensure_versions=True,persist_event=True)
        assert result.analysis_status=="ingest_failed"
        assert all(error.startswith("incomplete_version:") for error in result.errors)
    _cleanup()

def test_phase43_force_reanalysis_reuses_event_but_runs_analysis():
    _cleanup()
    with SessionLocal() as db:
        _doc(db,FROM,date(2025,1,1),[("1","title","old")]); _doc(db,TO,date(2026,1,1),[("1","title","new")])
        first=execute_phase43(db,object(),_selection(),ensure_versions=False,persist_event=True)
        second=execute_phase43(db,object(),_selection(),ensure_versions=False,persist_event=True,force_reanalyze=True)
        assert first.event.id==second.event.id and second.impact is not None and second.content_changed
    _cleanup()

def test_phase43_changed_without_mapping_has_distinct_warning():
    _cleanup()
    with SessionLocal() as db:
        _doc(db,FROM,date(2025,1,1),[("1","title","old")]); _doc(db,TO,date(2026,1,1),[("1","title","new")])
        result=execute_phase43(db,object(),_selection(),ensure_versions=False,persist_event=False)
        assert result.content_changed and result.impacted_rules==[]
        assert "changed_articles_have_no_rule_mapping" in result.warnings
    _cleanup()

def test_phase43_persist_false_does_not_create_aggregate_event():
    _cleanup()
    with SessionLocal() as db:
        _doc(db,FROM,date(2025,1,1),[("1","title","same")]); _doc(db,TO,date(2026,1,1),[("1","title","same")])
        result=execute_phase43(db,object(),_selection(),ensure_versions=False,persist_event=False)
        assert result.event is None and result.analysis_status=="no_change"
        assert db.scalar(select(func.count()).select_from(LiveLawChangeEvent).where(LiveLawChangeEvent.law_name==LAW))==0
    _cleanup()
