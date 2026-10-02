"""Unlinked municipalities keep the existing standard analysis and save contract.

No production database or external ordinance source is used. Existing law-data
enrichment is stubbed; the real analyzer and analysis persistence execute.
"""
import importlib

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.main import app
from app.models.analysis_result import AnalysisResult
from app.models.project import Project
from app.schemas.analyze import AnalyzeRequest
from app.services.analyzer import analyze_project


@pytest.fixture()
def client(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine, tables=[Project.__table__, AnalysisResult.__table__])
    factory = sessionmaker(bind=engine)

    def get_test_db():
        with factory() as db:
            yield db

    endpoint = importlib.import_module("app.api.analyze")
    for name in ("attach_legal_references", "attach_assessment_legal_references", "attach_article_candidates_to_analysis"):
        monkeypatch.setattr(endpoint, name, lambda **kwargs: None)
    previous = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = get_test_db
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        if previous is None:
            app.dependency_overrides.pop(get_db, None)
        else:
            app.dependency_overrides[get_db] = previous
        engine.dispose()


def payload(municipality):
    return dict(project_name="TEST_PHASE62_DO_NOT_USE", location="TEST_LOCATION_DO_NOT_USE",
                area_square_meters=100000, implementation_method="mixed", implementer_type="public",
                local_government=municipality, as_of="2099-06-15")


@pytest.mark.parametrize("municipality", ["TEST_UNLINKED_A_DO_NOT_USE", "TEST_UNLINKED_B_DO_NOT_USE", ""])
def test_unlinked_region_analyzes_and_saves_standard_result(client, municipality):
    request = payload(municipality)
    expected = analyze_project(AnalyzeRequest(**request)).model_dump(mode="json")
    response = client.post("/api/analyze", json=request)
    assert response.status_code == 200
    result = response.json()
    assert result["local_government"] == municipality
    for field in ("procedures", "standard_procedure_graph", "assessments"):
        assert result[field] == expected[field]
    assert result["procedures"] and result["assessments"]
    assert any(item["local_rule_required"] for item in result["assessments"])
    assert not any(key.startswith("ordinance") for key in result)
    saved = client.get(f"/api/analyses/{result['analysis_id']}")
    assert saved.status_code == 200
    assert saved.json()["result_payload"] == result


def test_region_name_does_not_invent_local_rules():
    left = analyze_project(AnalyzeRequest(**payload("TEST_UNLINKED_A_DO_NOT_USE")))
    right = analyze_project(AnalyzeRequest(**payload("TEST_UNLINKED_B_DO_NOT_USE")))
    assert left.procedures == right.procedures
    assert left.standard_procedure_graph == right.standard_procedure_graph
    assert left.assessments == right.assessments


def test_invalid_analysis_remains_validation_error(client):
    request = payload("TEST_UNLINKED_DO_NOT_USE")
    request["area_square_meters"] = -1
    assert client.post("/api/analyze", json=request).status_code == 422
