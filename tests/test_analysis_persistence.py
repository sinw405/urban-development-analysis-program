from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def create_analysis(project_name: str, local_government: str = "Seongnam-si") -> dict:
    response = client.post(
        "/api/analyze",
        json={
            "project_name": project_name,
            "location": "Seongnam-si, Gyeonggi-do",
            "area_square_meters": 12345,
            "implementation_method": "Expropriation or use method",
            "implementer_type": "Local public corporation",
            "local_government": local_government,
        },
    )
    assert response.status_code == 200
    return response.json()


def test_list_and_get_analysis_results():
    created = create_analysis("Persistence Detail Test Project")
    analysis_id = created["analysis_id"]

    list_response = client.get("/api/analyses")
    assert list_response.status_code == 200
    list_data = list_response.json()
    assert set(list_data) == {"items", "total", "limit", "offset"}
    assert list_data["limit"] == 20
    assert list_data["offset"] == 0
    assert list_data["total"] >= 1
    assert any(item["analysis_id"] == analysis_id for item in list_data["items"])

    detail_response = client.get(f"/api/analyses/{analysis_id}")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["analysis_id"] == analysis_id
    assert detail["project_id"] == created["project_id"]
    assert detail["request_payload"]["project_name"] == "Persistence Detail Test Project"
    assert detail["result_payload"]["analysis_id"] == analysis_id
    assert detail["result_payload"]["project_id"] == created["project_id"]
    assert detail["result_payload"]["created_at"] is not None
    assert len(detail["result_payload"]["procedures"]) > 0
    first_step = detail["result_payload"]["procedures"][0]
    assert "step_code" in first_step
    assert "step_name" in first_step
    assert "sequence" in first_step
    assert "legal_basis_placeholder" in first_step
    assert first_step["legal_references"] == []
    assert "order" not in first_step
    assert "legal_basis" not in first_step
    assert len(detail["result_payload"]["assessments"]) == 8


def test_analysis_list_pagination_total_and_sort():
    first = create_analysis("Pagination Sort Test A", "Pagination-si")
    second = create_analysis("Pagination Sort Test B", "Pagination-si")

    response = client.get("/api/analyses?limit=1&offset=0&project_name=Pagination Sort Test")
    assert response.status_code == 200
    data = response.json()
    assert data["limit"] == 1
    assert data["offset"] == 0
    assert data["total"] >= 2
    assert len(data["items"]) == 1

    asc_response = client.get(
        "/api/analyses?limit=10&offset=0&project_name=Pagination Sort Test&sort=created_at_asc"
    )
    assert asc_response.status_code == 200
    asc_items = asc_response.json()["items"]
    ids = [item["analysis_id"] for item in asc_items if item["analysis_id"] in {first["analysis_id"], second["analysis_id"]}]
    assert ids == sorted(ids)


def test_analysis_list_project_name_filter():
    created = create_analysis("Unique Project Name Filter Case", "Filter-si")

    response = client.get("/api/analyses?project_name=Unique Project Name Filter")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    assert any(item["analysis_id"] == created["analysis_id"] for item in data["items"])


def test_analysis_list_local_government_filter():
    created = create_analysis("Local Government Filter Case", "FilterLocalGov-si")

    response = client.get("/api/analyses?local_government=FilterLocalGov")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    assert all("FilterLocalGov" in item["local_government"] for item in data["items"])
    assert any(item["analysis_id"] == created["analysis_id"] for item in data["items"])


def test_get_missing_analysis_returns_404():
    response = client.get("/api/analyses/999999999")
    assert response.status_code == 404


def test_stored_assessment_thresholds_remain_placeholders():
    created = create_analysis("Placeholder Persistence Test Project")
    detail_response = client.get(f"/api/analyses/{created['analysis_id']}")
    assert detail_response.status_code == 200
    detail = detail_response.json()

    assessments = detail["result_payload"]["assessments"]
    assert len(assessments) == 8
    for item in assessments:
        assert item["threshold"] == "TODO_PLACEHOLDER_DO_NOT_USE_AS_CRITERIA"
        assert item["legal_basis"] == "TODO_MOLEG_API_ARTICLE_CHECK"
        assert "\ub300\uc0c1 \ud655\uc815" not in item["status"]
        assert "\ube44\ub300\uc0c1 \ud655\uc815" not in item["status"]
