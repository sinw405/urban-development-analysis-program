import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.main import app
from app.models.analysis_result import AnalysisResult
from app.models.development_case import DevelopmentCase
from app.models.project import Project
from app.schemas.analyze import AnalyzeResponse
from app.schemas.reference_validation import ReferenceCaseValidationInput


@pytest.fixture()
def case_client():
    engine = create_engine(
        'sqlite://',
        connect_args={'check_same_thread': False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(
        engine,
        tables=[Project.__table__, AnalysisResult.__table__, DevelopmentCase.__table__],
    )
    sessions = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def override_db():
        with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as client:
        yield client, sessions
    app.dependency_overrides.pop(get_db, None)


def draft_payload():
    return {
        'name': 'TEST case draft',
        'location': None,
        'area_m2': None,
        'method': None,
        'operator_type': None,
        'timeline': [],
        'history': [],
        'data_classification': 'DRAFT',
        'provenance': {'verification_status': 'UNVERIFIED'},
    }


def add_project(sessions):
    with sessions() as db:
        project = Project(
            project_name='TEST project',
            location='TEST location',
            area_square_meters=1,
            implementation_method='TEST method',
            implementer_type='TEST operator',
            local_government='TEST government',
        )
        db.add(project)
        db.commit()
        db.refresh(project)
        return project.id


def test_register_read_and_compare_draft_case(case_client):
    client, sessions = case_client
    response = client.post('/api/cases', json=draft_payload())
    assert response.status_code == 201
    created = response.json()
    assert created['data_classification'] == 'DRAFT'
    assert created['area_m2'] is None

    case_id = created['id']
    detail = client.get(f'/api/cases/{case_id}')
    assert detail.status_code == 200
    project_id = add_project(sessions)
    comparison = client.get(f'/api/cases?similar_to={project_id}')
    assert comparison.status_code == 200
    assert comparison.json()['items'][0]['id'] == created['id']


@pytest.mark.parametrize(
    'payload',
    [
        {},
        {'name': ''},
        {'name': 'TEST', 'area_m2': 0},
        {'name': 'TEST', 'timeline': [{}]},
        {'name': 'TEST', 'timeline': [{'stage': ''}]},
        {'name': 'TEST', 'unknown_field': 'TEST'},
    ],
)
def test_malformed_case_payload_is_rejected(case_client, payload):
    client, _ = case_client
    assert client.post('/api/cases', json=payload).status_code == 422


def test_test_fixture_classification_is_rejected_and_not_seeded(case_client):
    client, sessions = case_client
    payload = draft_payload()
    payload['data_classification'] = 'TEST_SAMPLE_FIXTURE'
    assert client.post('/api/cases', json=payload).status_code == 422
    with sessions() as db:
        assert db.scalars(select(DevelopmentCase)).all() == []


def test_verified_reference_requires_complete_verified_provenance(case_client):
    client, _ = case_client
    payload = draft_payload()
    payload['data_classification'] = 'VERIFIED_REFERENCE'
    assert client.post('/api/cases', json=payload).status_code == 422


def verified_payload():
    payload = draft_payload()
    payload.update(
        {
            'location': 'TEST verified location',
            'area_m2': 1,
            'method': 'TEST verified method',
            'operator_type': 'TEST verified operator',
            'timeline': [{'stage': 'TEST verified step', 'date': '2026-01-01'}],
            'data_classification': 'VERIFIED_REFERENCE',
            'provenance': {
                'source_title': 'TEST source',
                'source_type': 'TEST document',
                'source_reference': 'TEST reference',
                'verified_at': '2026-01-02T00:00:00Z',
                'verification_status': 'VERIFIED',
            },
        }
    )
    return payload


def test_verified_case_registration_and_safe_update(case_client):
    client, _ = case_client
    created = client.post('/api/cases', json=verified_payload())
    assert created.status_code == 201
    case_id = created.json()['id']
    updated = client.patch(f'/api/cases/{case_id}', json={'name': 'TEST updated'})
    assert updated.status_code == 200
    assert updated.json()['name'] == 'TEST updated'
    invalid = client.patch(
        f'/api/cases/{case_id}',
        json={'provenance': {'verification_status': 'UNVERIFIED'}},
    )
    assert invalid.status_code == 422


def test_existing_contracts_remain_separate():
    analyze_fields = set(AnalyzeResponse.model_fields)
    reference_fields = set(ReferenceCaseValidationInput.model_fields)
    assert 'cases' not in analyze_fields
    assert 'data_classification' in reference_fields
