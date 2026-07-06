from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_analyze_returns_procedures_and_placeholder_assessments():
    response = client.post(
        "/api/analyze",
        json={
            "project_name": "Test Urban Development Project",
            "location": "Seongnam-si, Gyeonggi-do",
            "area_square_meters": 100000,
            "implementation_method": "Expropriation or use method",
            "implementer_type": "Local public corporation",
            "local_government": "Seongnam-si",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["project_name"] == "Test Urban Development Project"
    assert len(data["procedures"]) > 0
    assert len(data["assessments"]) == 4

    for item in data["assessments"]:
        assert "TODO" in item["threshold"]
        assert "TODO" in item["legal_basis"]
