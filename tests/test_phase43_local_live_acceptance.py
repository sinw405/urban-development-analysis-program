from scripts.phase43_local_live_acceptance import REPORT_FIELDS, empty_report, fail, render_report


def test_phase43_local_acceptance_report_schema_and_pass_rendering():
    report = empty_report()
    report["FINAL RESULT"] = "PASS"
    rendered = render_report(report)
    assert rendered.startswith("PHASE 43 LOCAL LIVE ACCEPTANCE")
    assert list(report) == REPORT_FIELDS
    assert "31. FINAL RESULT: PASS" in rendered


def test_phase43_local_acceptance_fail_mapping_and_no_secret(capsys):
    report = empty_report()
    assert fail(report, "discovery") == 1
    rendered = capsys.readouterr().out
    assert "FINAL RESULT: FAIL: discovery" in rendered
    assert "MOLEG_API_KEY" not in rendered
    assert "OC=" not in rendered
