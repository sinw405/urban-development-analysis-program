from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def create_analysis() -> dict:
    response = client.post(
        "/api/analyze",
        json={
            "project_name": "Persistence Test Project",
            "location": "Seongnam-si, Gyeonggi-do",
            "area_square_meters": 12345,
            "implementation_method": "Expropriation or use method",
            "implementer_type": "Local public corporation",
            "local_government": "Seongnam-si",
        },
    )
    assert response.status_code == 200
    return response.json()


def test_list_and_get_analysis_results():
    created = create_analysis()
    analysis_id = created["analysis_id"]

    list_response = client.get("/api/analyses")
    assert list_response.status_code == 200
    analyses = list_response.json()
    assert any(item["analysis_id"] == analysis_id for item in analyses)

    detail_response = client.get(f"/api/analyses/{analysis_id}")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["analysis_id"] == analysis_id
    assert detail["project_id"] == created["project_id"]
    assert detail["request_payload"]["project_name"] == "Persistence Test Project"
    assert detail["result_payload"]["analysis_id"] == analysis_id
    assert detail["result_payload"]["project_id"] == created["project_id"]
    assert detail["result_payload"]["created_at"] is not None
    assert len(detail["result_payload"]["procedures"]) > 0
    assert len(detail["result_payload"]["assessments"]) == 4


def test_get_missing_analysis_returns_404():
    response = client.get("/api/analyses/999999999")
    assert response.status_code == 404
