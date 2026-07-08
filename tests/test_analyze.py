from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_analyze_returns_phase2_procedure_structure_and_persistence_ids():
    response = client.post(
        "/api/analyze",
        json={
            "project_name": "Test Urban Development Project",
            "location": "Seongnam-si, Gyeonggi-do",
            "area_square_meters": 100000,
            "implementation_method": "expropriation_or_use",
            "implementer_type": "public",
            "local_government": "Seongnam-si",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["project_name"] == "Test Urban Development Project"
    assert isinstance(data["project_id"], int)
    assert isinstance(data["analysis_id"], int)
    assert data["created_at"] is not None
    assert len(data["procedures"]) > 0

    expected_fields = {
        "step_code",
        "step_name",
        "sequence",
        "description",
        "required_documents",
        "related_agencies",
        "estimated_duration",
        "legal_basis_placeholder",
        "legal_references",
        "legal_reference_status",
        "notes",
    }
    assert set(data["procedures"][0]) == expected_fields
    assert "order" not in data["procedures"][0]
    assert "name" not in data["procedures"][0]
    assert "legal_basis" not in data["procedures"][0]
    assert "consultation_agencies" not in data["procedures"][0]

    for step in data["procedures"]:
        assert "TODO" in " ".join(step["legal_basis_placeholder"])
        assert step["legal_references"] == []
        assert step["legal_reference_status"] == "missing"

    for item in data["assessments"]:
        assert item["threshold"] == "TODO_PLACEHOLDER_DO_NOT_USE_AS_CRITERIA"
        assert item["legal_basis"] == "TODO_MOLEG_API_ARTICLE_CHECK"
        assert "\ub300\uc0c1 \ud655\uc815" not in item["status"]
        assert "\ube44\ub300\uc0c1 \ud655\uc815" not in item["status"]
