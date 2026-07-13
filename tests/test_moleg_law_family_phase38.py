from __future__ import annotations

import json
from datetime import date

import httpx
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.main import app
from app.models import Law, LawArticle, LawArticleVersion, OfficialLawArticleRecord, OfficialLawDocument, OfficialLawIngestRun, OfficialLawSourceEvidence, ProcedureLegalReference
from app.services.moleg_live_client import MOLEG_LAW_SEARCH_PATH, MOLEG_LAW_SERVICE_PATH
from app.services.moleg_live_ingest_service import LAW_FAMILY_URBAN_DEVELOPMENT, run_moleg_law_family_ingest, run_moleg_live_ingest, select_law_version_candidates
from app.services.moleg_version_diff_service import diff_moleg_versions
from app.services.official_law_source import MolegOpenApiLawSourceProvider

client = TestClient(app)
SECRET = "TEST_PHASE38_SECRET_DO_NOT_USE"
LAW_NAMES = ["Dummy Family Act", "Dummy Family Decree", "Dummy Family Rule"]
LAW_IDS = {"Dummy Family Act": "DUMMY-ACT-38", "Dummy Family Decree": "DUMMY-DECREE-38", "Dummy Family Rule": "DUMMY-RULE-38"}
MSTS = {"Dummy Family Act": ["DUMMY-ACT-MST-CURRENT", "DUMMY-ACT-MST-OLD", "DUMMY-ACT-MST-FUTURE"], "Dummy Family Decree": ["DUMMY-DECREE-MST-CURRENT"], "Dummy Family Rule": ["DUMMY-RULE-MST-CURRENT"]}


def _enable(monkeypatch):
    monkeypatch.setenv("MOLEG_API_ENABLED", "true")
    monkeypatch.setenv("MOLEG_LIVE_TEST_ENABLED", "true")
    monkeypatch.setenv("MOLEG_API_BASE_URL", "https://www.law.go.kr")
    monkeypatch.setenv("MOLEG_API_KEY", SECRET)
    get_settings.cache_clear()


def _search_xml(name: str) -> str:
    law_id = LAW_IDS[name]
    if name == "Dummy Family Act":
        laws = [
            (name + " Similar", "SIMILAR-MST", "SIMILAR-ID", "20990101"),
            (name, MSTS[name][0], law_id, "20990101"),
            (name, MSTS[name][1], law_id, "20980101"),
            (name, MSTS[name][2], law_id, "21000101"),
        ]
    else:
        laws = [(name, MSTS[name][0], law_id, "20990101")]
    body = "".join(
        f"<law><법령명한글><![CDATA[{title}]]></법령명한글><법령일련번호>{mst}</법령일련번호><법령ID>{law_id_value}</법령ID><법령구분명>Dummy Type</법령구분명><현행연혁코드>현행</현행연혁코드><시행일자>{eff}</시행일자><법령상세링크>/DRF/lawService.do?OC={SECRET}&amp;target=law&amp;MST={mst}&amp;type=HTML&amp;efYd={eff}</법령상세링크></law>"
        for title, mst, law_id_value, eff in laws
    )
    return f"<LawSearch><totalCnt>{len(laws)}</totalCnt><page>1</page><numOfRows>{len(laws)}</numOfRows><resultCode>00</resultCode><resultMsg>success</resultMsg>{body}</LawSearch>"


def _detail_xml(name: str, mst: str) -> str:
    law_id = LAW_IDS[name]
    effective = "20980101" if mst.endswith("OLD") else "21000101" if mst.endswith("FUTURE") else "20990101"
    article_2 = "Updated body" if mst.endswith("CURRENT") else "Old body" if mst.endswith("OLD") else "Future body"
    extra = "<조문단위><조문번호>DUMMY-003</조문번호><조문제목>Future Added</조문제목><조문내용>Future added body.</조문내용></조문단위>" if mst.endswith("FUTURE") else ""
    removed = "" if mst.endswith("FUTURE") else "<조문단위><조문번호>DUMMY-001</조문번호><조문제목>Stable</조문제목><조문내용>Stable body.</조문내용></조문단위>"
    return f"""<법령><기본정보><법령명한글>{name}</법령명한글><법령ID>{law_id}</법령ID><시행일자>{effective}</시행일자></기본정보><조문>{removed}<조문단위><조문번호>DUMMY-002</조문번호><조문제목>Changed</조문제목><조문내용>{article_2}</조문내용></조문단위>{extra}</조문></법령>"""


def _xml_response(url: str, text: str) -> httpx.Response:
    return httpx.Response(200, text=text, headers={"content-type": "application/xml"}, request=httpx.Request("GET", url))


def _mock(monkeypatch, fail_name: str | None = None):
    def fake_get(url, params, **kwargs):
        if MOLEG_LAW_SEARCH_PATH in url:
            query = params["query"]
            if query == fail_name:
                raise httpx.ConnectError("phase38 mocked connection error")
            return _xml_response(url, _search_xml(query))
        if MOLEG_LAW_SERVICE_PATH in url:
            mst = params["MST"]
            for name, values in MSTS.items():
                if mst in values:
                    return _xml_response(url, _detail_xml(name, mst))
            raise AssertionError(mst)
        raise AssertionError(url)
    monkeypatch.setattr(httpx, "get", fake_get)


def _cleanup():
    db = SessionLocal()
    try:
        law_keys = [f"moleg:{law_id}" for law_id in LAW_IDS.values()]
        law_ids = list(db.scalars(select(Law.id).where(Law.law_key.in_(law_keys))).all())
        if law_ids:
            article_ids = list(db.scalars(select(LawArticle.id).where(LawArticle.law_id.in_(law_ids))).all())
            db.execute(delete(ProcedureLegalReference).where(ProcedureLegalReference.law_id.in_(law_ids)))
            if article_ids:
                db.execute(delete(ProcedureLegalReference).where(ProcedureLegalReference.law_article_id.in_(article_ids)))
                db.execute(delete(LawArticleVersion).where(LawArticleVersion.law_article_id.in_(article_ids)))
                db.execute(delete(LawArticle).where(LawArticle.id.in_(article_ids)))
            db.execute(delete(Law).where(Law.id.in_(law_ids)))
        all_msts = [mst for values in MSTS.values() for mst in values]
        doc_ids = list(db.scalars(select(OfficialLawDocument.id).where(OfficialLawDocument.mst.in_(all_msts))).all())
        if doc_ids:
            db.execute(delete(OfficialLawArticleRecord).where(OfficialLawArticleRecord.document_id.in_(doc_ids)))
            db.execute(delete(OfficialLawDocument).where(OfficialLawDocument.id.in_(doc_ids)))
        run_ids = list(db.scalars(select(OfficialLawIngestRun.id).where(OfficialLawIngestRun.query.in_(LAW_NAMES))).all())
        if run_ids:
            db.execute(delete(OfficialLawSourceEvidence).where(OfficialLawSourceEvidence.ingest_run_id.in_(run_ids)))
            db.execute(delete(OfficialLawIngestRun).where(OfficialLawIngestRun.id.in_(run_ids)))
        db.commit()
    finally:
        db.close()


def _counts():
    db = SessionLocal()
    try:
        law_keys = [f"moleg:{law_id}" for law_id in LAW_IDS.values()]
        return {
            "laws": db.scalar(select(func.count()).select_from(Law).where(Law.law_key.in_(law_keys))) or 0,
            "articles": db.scalar(select(func.count()).select_from(LawArticle).join(Law).where(Law.law_key.in_(law_keys))) or 0,
            "versions": db.scalar(select(func.count()).select_from(LawArticleVersion).join(LawArticle).join(Law).where(Law.law_key.in_(law_keys))) or 0,
            "raw_versions": db.scalar(select(func.count()).select_from(LawArticleVersion).join(LawArticle).join(Law).where(Law.law_key.in_(law_keys), LawArticleVersion.raw_payload_json.is_not(None))) or 0,
        }
    finally:
        db.close()


def test_phase38_exact_version_selection_distinguishes_laws():
    provider = MolegOpenApiLawSourceProvider(base_url="http://www.law.go.kr", api_key=SECRET)
    result = provider._normalize_law_search_result(payload={"LawSearch": {"law": [{"법령명한글": "Dummy Family Act Enforcement Decree", "법령일련번호": "X", "법령ID": "X", "시행일자": "20990101"}, {"법령명한글": "Dummy Family Act", "법령일련번호": "Y", "법령ID": "Y", "시행일자": "20990101"}]}}, query="Dummy Family Act")
    selected = select_law_version_candidates(result, "Dummy Family Act", include_history=1)
    assert len(selected) == 1
    assert selected[0][0].title == "Dummy Family Act"


def test_phase38_family_dry_run_apply_idempotency_and_rollback(monkeypatch):
    _cleanup(); _enable(monkeypatch); _mock(monkeypatch)
    import app.services.moleg_live_ingest_service as service
    monkeypatch.setitem(service.LAW_FAMILY_REGISTRY, LAW_FAMILY_URBAN_DEVELOPMENT, LAW_NAMES)
    before = _counts()
    dry = run_moleg_law_family_ingest(SessionLocal, LAW_FAMILY_URBAN_DEVELOPMENT, dry_run=True, include_history=1)
    assert dry.status == "ready"
    assert _counts() == before
    applied = run_moleg_law_family_ingest(SessionLocal, LAW_FAMILY_URBAN_DEVELOPMENT, dry_run=False, include_history=1)
    assert applied.status == "completed"
    assert _counts()["laws"] == 3
    second = run_moleg_law_family_ingest(SessionLocal, LAW_FAMILY_URBAN_DEVELOPMENT, dry_run=False, include_history=1)
    assert all(item.counters.inserted_law_count == 0 for item in second.results)
    rolled = run_moleg_law_family_ingest(SessionLocal, LAW_FAMILY_URBAN_DEVELOPMENT, dry_run=False, include_history=1, force_rollback_after_persist=True)
    assert rolled.status == "failed"
    assert _counts()["raw_versions"] == 0
    dumped = json.dumps(applied.to_dict(), ensure_ascii=False, default=str)
    assert SECRET not in dumped
    _cleanup(); get_settings.cache_clear()


def test_phase38_as_of_coverage_and_version_diff(monkeypatch):
    _cleanup(); _enable(monkeypatch); _mock(monkeypatch)
    db = SessionLocal()
    try:
        result = run_moleg_live_ingest(db, "Dummy Family Act", dry_run=False, include_history=1)
        assert result.status == "completed"
        law = db.scalar(select(Law).where(Law.law_key == f"moleg:{LAW_IDS['Dummy Family Act']}"))
        old = client.get(f"/api/laws/{law.id}/articles?as_of=2097-01-01").json()
        covered = client.get(f"/api/laws/{law.id}/articles?as_of=2098-01-01").json()
        current = client.get(f"/api/laws/{law.id}/articles?as_of=2099-01-01").json()
        assert old["coverage_status"] == "before_available_history"
        assert old["current_version_count"] == 0
        assert covered["coverage_status"] == "covered"
        assert current["coverage_status"] == "covered"
        diff = diff_moleg_versions(db, "Dummy Family Act", MSTS["Dummy Family Act"][1], MSTS["Dummy Family Act"][0])
        assert diff.status == "ok"
        assert len(diff.changed) == 1
        assert len(diff.unchanged) == 1
        future_diff = diff_moleg_versions(db, "Dummy Family Act", MSTS["Dummy Family Act"][0], MSTS["Dummy Family Act"][2])
        assert len(future_diff.added) == 1
        assert len(future_diff.removed) == 1
    finally:
        db.close(); _cleanup(); get_settings.cache_clear()


def test_phase38_regressions_keep_analyze_and_diagnostic(monkeypatch):
    _enable(monkeypatch); _mock(monkeypatch)
    diagnostic = client.get("/api/legal-references/moleg/diagnostic")
    assert diagnostic.status_code == 200
    analyze = client.post("/api/analyze", json={"project_name": "Phase38 Analyze Smoke", "location": "Test", "area_square_meters": 100000, "implementation_method": "expropriation_or_use", "implementer_type": "public", "local_government": "Test LG"})
    assert analyze.status_code == 200
    assert len(analyze.json()["procedures"]) == 13
    get_settings.cache_clear()