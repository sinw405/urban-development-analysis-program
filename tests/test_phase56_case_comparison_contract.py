from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.main import app
from app.models.analysis_result import AnalysisResult
from app.models.development_case import DevelopmentCase
from app.models.project import Project
from app.schemas.analyze import AnalyzeResponse


@pytest.fixture()
def case_client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(
        engine,
        tables=[Project.__table__, AnalysisResult.__table__, DevelopmentCase.__table__],
    )
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def override_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as client:
        yield client, session_factory
    app.dependency_overrides.pop(get_db, None)
    Base.metadata.drop_all(
        engine,
        tables=[DevelopmentCase.__table__, AnalysisResult.__table__, Project.__table__],
    )


def add_project(session_factory, name="TEST/SAMPLE current project"):
    with session_factory() as db:
        project = Project(
            project_name=name,
            location="TEST/SAMPLE location",
            area_square_meters=1,
            implementation_method="TEST/SAMPLE method",
            implementer_type="TEST/SAMPLE operator type",
            local_government="TEST/SAMPLE local government",
        )
        db.add(project)
        db.commit()
        db.refresh(project)
        return project.id


def test_cases_endpoint_returns_empty_collection_for_registered_project(case_client):
    client, session_factory = case_client
    project_id = add_project(session_factory)

    response = client.get(f"/api/cases?similar_to={project_id}")

    assert response.status_code == 200
    assert response.json() == {"items": []}


def test_cases_endpoint_rejects_missing_project(case_client):
    client, _ = case_client
    response = client.get("/api/cases?similar_to=999999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Project not found"


def test_cases_endpoint_preserves_nullable_fields_and_two_sample_cases(case_client):
    client, session_factory = case_client
    project_id = add_project(session_factory)
    with session_factory() as db:
        db.add_all(
            [
                DevelopmentCase(
                    name="TEST/SAMPLE/FIXTURE case A",
                    location=None,
                    area_m2=None,
                    method=None,
                    operator_type=None,
                    timeline=[],
                    history=[],
                    created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
                ),
                DevelopmentCase(
                    name="TEST/SAMPLE/FIXTURE case B",
                    location="TEST/SAMPLE region",
                    area_m2=0,
                    method="",
                    operator_type="TEST/SAMPLE operator",
                    timeline=[
                        {
                            "stage": "TEST/SAMPLE later stage",
                            "date": "2026-02-01",
                            "status": "TEST",
                            "description": "TEST/SAMPLE description",
                        }
                    ],
                    history=[
                        {
                            "stage": "TEST/SAMPLE earlier stage",
                            "date": "2026-01-01",
                            "status": None,
                            "description": None,
                        }
                    ],
                    created_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
                ),
            ]
        )
        db.commit()

    response = client.get(f"/api/cases?similar_to={project_id}")

    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 2
    nullable = next(item for item in items if item["name"].endswith("case A"))
    assert nullable["location"] is None
    assert nullable["area_m2"] is None
    assert nullable["timeline"] == []
    populated = next(item for item in items if item["name"].endswith("case B"))
    assert populated["area_m2"] == 0
    assert populated["method"] == ""
    assert populated["timeline"][0]["date"] == "2026-02-01"
    assert populated["history"][0]["date"] == "2026-01-01"
    assert set(populated) == {
        "id", "name", "location", "area_m2", "method", "operator_type", "timeline", "history"
    }


def test_existing_analyze_contract_has_no_case_fields():
    fields = set(AnalyzeResponse.model_fields)
    assert "cases" not in fields
    assert "similar_cases" not in fields
    assert {"project_id", "analysis_id", "procedures", "assessments"} <= fields
