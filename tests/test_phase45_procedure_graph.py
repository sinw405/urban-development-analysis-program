from copy import deepcopy

import pytest

from app.schemas.analyze import AnalyzeRequest
from app.services.analyzer import _build_standard_graph, analyze_project
from app.services.rule_loader import load_yaml_rule


EXPECTED_STAGES = [
    ("ZONE_DESIGNATION_PROPOSAL", "구역지정 제안"),
    ("ZONE_DESIGNATION_NOTIFICATION", "구역 지정·고시"),
    ("DEVELOPMENT_PLAN", "개발계획"),
    ("IMPLEMENTATION_PLAN_AUTHORIZATION", "실시계획 인가"),
    ("PROJECT_IMPLEMENTATION", "사업시행"),
    ("COMPLETION", "준공"),
]


def _analyze(method: str = "mixed", implementer: str = "public_private_spc"):
    return analyze_project(
        AnalyzeRequest(
            project_name="TEST_PHASE45_FIXTURE_DO_NOT_USE",
            location="TEST_LOCATION_DO_NOT_USE",
            area_square_meters=1,
            implementation_method=method,
            implementer_type=implementer,
            local_government="TEST_LOCAL_GOVERNMENT_DO_NOT_USE",
        )
    )


def test_standard_graph_has_stable_six_stage_order_and_dependencies():
    result = _analyze()
    graph = result.standard_procedure_graph

    assert [(stage.stage_code, stage.stage_name) for stage in graph] == EXPECTED_STAGES
    assert [stage.sequence for stage in graph] == [10, 20, 30, 40, 50, 60]
    assert graph[0].depends_on == []
    for previous, current in zip(graph, graph[1:]):
        assert current.depends_on == [previous.stage_code]


def test_every_selected_detail_step_maps_to_one_standard_stage():
    result = _analyze()
    mapped_codes = [code for stage in result.standard_procedure_graph for code in stage.detail_step_codes]

    assert sorted(mapped_codes) == sorted(step.step_code for step in result.procedures)
    assert len(mapped_codes) == len(set(mapped_codes))
    assert all(step.standard_stage_code for step in result.procedures)
    assert result.procedures[0].depends_on == []
    assert all(len(step.depends_on) == 1 for step in result.procedures[1:])


@pytest.mark.parametrize(
    ("method", "expected_step"),
    [
        ("expropriation_or_use", "LAND_ACQUISITION_REVIEW"),
        ("replotting", "REPLOTTING_PLAN_REVIEW"),
        ("mixed", "MIXED_METHOD_COORDINATION"),
    ],
)
def test_method_branch_is_preserved_inside_implementation_plan_stage(method, expected_step):
    result = _analyze(method=method, implementer="public")
    stage = next(
        item for item in result.standard_procedure_graph
        if item.stage_code == "IMPLEMENTATION_PLAN_AUTHORIZATION"
    )

    assert expected_step in stage.detail_step_codes


def test_unconfirmed_standard_stage_legal_basis_is_explicitly_unresolved():
    result = _analyze()

    assert all(stage.legal_basis_status == "unresolved" for stage in result.standard_procedure_graph)
    assert all(step.legal_basis_placeholder for step in result.procedures)
    assert all(step.legal_references == [] for step in result.procedures)


def test_rule_validation_rejects_unknown_dependency():
    rules = deepcopy(load_yaml_rule("procedure_rules.yaml"))
    rules["standard_procedure_graph"][0]["depends_on"] = ["UNKNOWN_STAGE"]
    procedures = _analyze().procedures

    with pytest.raises(ValueError, match="unknown standard stage dependencies"):
        _build_standard_graph(rules, procedures)


def test_rule_validation_rejects_unmapped_configured_step():
    rules = deepcopy(load_yaml_rule("procedure_rules.yaml"))
    rules["standard_procedure_graph"][0]["detail_step_codes"].remove("PROJECT_BASIC_REVIEW")
    procedures = _analyze().procedures

    with pytest.raises(ValueError, match="must match configured procedure steps"):
        _build_standard_graph(rules, procedures)
