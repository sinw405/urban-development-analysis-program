from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def analyze(implementation_method: str, implementer_type: str, project_name: str = "Rule Engine Test") -> dict:
    response = client.post(
        "/api/analyze",
        json={
            "project_name": project_name,
            "location": "Seongnam-si, Gyeonggi-do",
            "area_square_meters": 100000,
            "implementation_method": implementation_method,
            "implementer_type": implementer_type,
            "local_government": "Seongnam-si",
        },
    )
    assert response.status_code == 200
    return response.json()


def step_codes(data: dict) -> set[str]:
    return {step["step_code"] for step in data["procedures"]}


def test_common_steps_are_returned():
    data = analyze("expropriation_or_use", "public")
    codes = step_codes(data)

    assert "PROJECT_BASIC_REVIEW" in codes
    assert "RELATED_AGENCY_CONSULTATION" in codes
    assert "IMPLEMENTER_DESIGNATION_REVIEW" in codes
    assert "COMPLETION_INSPECTION" in codes


def test_implementation_method_expropriation_or_use_branch():
    data = analyze("수용 또는 사용 방식", "public")

    assert "LAND_ACQUISITION_REVIEW" in step_codes(data)


def test_implementation_method_replotting_branch():
    data = analyze("환지", "public")

    assert "REPLOTTING_PLAN_REVIEW" in step_codes(data)


def test_implementation_method_mixed_branch():
    data = analyze("혼용 방식", "public")

    assert "MIXED_METHOD_COORDINATION" in step_codes(data)


def test_implementer_type_public_branch():
    data = analyze("expropriation_or_use", "공공")

    assert "PUBLIC_IMPLEMENTER_COORDINATION" in step_codes(data)


def test_implementer_type_private_branch():
    data = analyze("expropriation_or_use", "민간")

    assert "PRIVATE_IMPLEMENTER_QUALIFICATION_REVIEW" in step_codes(data)


def test_implementer_type_public_private_spc_branch():
    data = analyze("expropriation_or_use", "민관협동 SPC")

    assert "SPC_GOVERNANCE_REVIEW" in step_codes(data)


def test_sequences_are_sorted():
    data = analyze("mixed", "public_private_spc")
    sequences = [step["sequence"] for step in data["procedures"]]

    assert sequences == sorted(sequences)


def test_unknown_branch_keeps_common_steps_and_adds_warning():
    data = analyze("unknown method", "unknown implementer")
    codes = step_codes(data)

    assert "PROJECT_BASIC_REVIEW" in codes
    assert "LAND_ACQUISITION_REVIEW" not in codes
    assert any("Unknown implementation_method" in warning for warning in data["warnings"])
    assert any("Unknown implementer_type" in warning for warning in data["warnings"])


def test_baekhyeon_mice_input_uses_generic_rule_engine_only():
    data = analyze("혼용", "민관SPC", project_name="백현마이스 도시개발사업")
    codes = step_codes(data)

    assert "MIXED_METHOD_COORDINATION" in codes
    assert "SPC_GOVERNANCE_REVIEW" in codes
    assert not any("BAEKHYEON" in code.upper() for code in codes)
    assert not any("MICE" in code.upper() for code in codes)

def test_core_common_procedure_coverage_after_phase18():
    data = analyze("unknown method", "unknown implementer")
    procedures = data["procedures"]
    codes = step_codes(data)

    assert len(procedures) == 11
    assert "IMPLEMENTER_DESIGNATION_REVIEW" in codes

    designation_step = next(step for step in procedures if step["step_code"] == "IMPLEMENTER_DESIGNATION_REVIEW")
    assert designation_step["required_documents"] == []
    assert designation_step["related_agencies"] == []
    assert designation_step["estimated_duration"] == "TODO_EXPERT_REVIEW"
    assert designation_step["legal_basis_placeholder"] == ["TODO_MOLEG_API_ARTICLE_CHECK"]
