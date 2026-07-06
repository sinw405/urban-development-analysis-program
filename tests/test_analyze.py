from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_analyze_returns_procedures_placeholder_assessments_and_persistence_ids():
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
    assert isinstance(data["project_id"], int)
    assert isinstance(data["analysis_id"], int)
    assert data["created_at"] is not None

    expected_status = "법령 검토 필요"
    expected_action_fragment = "기준 미확정"
    for item in data["assessments"]:
        assert item["status"] == expected_status
        assert item["threshold"] == "TODO_PLACEHOLDER_DO_NOT_USE_AS_CRITERIA"
        assert "TODO" in item["legal_basis"]
        assert expected_action_fragment in item["required_action"]
