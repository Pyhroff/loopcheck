"""End-to-end CLI tests against the real sample traces, via typer's test runner."""

import json

from typer.testing import CliRunner

from loopcheck.cli import app

runner = CliRunner()


def test_analyze_clean_trace_exits_zero():
    result = runner.invoke(app, ["analyze", "samples/clean_trace.json"])
    assert result.exit_code == 0
    assert "No waste detected" in result.stdout


def test_analyze_wasteful_trace_flags_duplicate_and_thrash():
    result = runner.invoke(app, ["analyze", "samples/wasteful_trace.json"])
    assert result.exit_code == 0
    assert "duplicate_calls" in result.stdout
    assert "loop_thrash" in result.stdout


def test_analyze_error_retry_trace_is_clean():
    result = runner.invoke(app, ["analyze", "samples/error_retry_trace.json"])
    assert result.exit_code == 0
    assert "No waste detected" in result.stdout


def test_fail_on_flag_exits_nonzero_when_findings_meet_threshold():
    result = runner.invoke(app, ["analyze", "samples/wasteful_trace.json", "--fail-on", "medium"])
    assert result.exit_code == 1


def test_fail_on_flag_exits_zero_on_clean_trace():
    result = runner.invoke(app, ["analyze", "samples/clean_trace.json", "--fail-on", "medium"])
    assert result.exit_code == 0


def test_json_output_written_and_valid(tmp_path):
    out = tmp_path / "report.json"
    result = runner.invoke(app, ["analyze", "samples/wasteful_trace.json", "--json", str(out)])
    assert result.exit_code == 0
    data = json.loads(out.read_text())
    assert data["agent_name"] == "research-bot"
    assert len(data["findings"]) >= 1


def test_missing_trace_file_exits_2():
    result = runner.invoke(app, ["analyze", "samples/does_not_exist.json"])
    assert result.exit_code == 2


def test_version_flag():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "0.6.0" in result.stdout


def test_judge_flag_without_api_key_skips_gracefully(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    result = runner.invoke(app, ["analyze", "samples/clean_trace.json", "--judge", "groq"])
    assert result.exit_code == 0
    assert "GROQ_API_KEY" in result.stdout


def test_judge_flag_with_unsupported_provider_skips_gracefully():
    result = runner.invoke(app, ["analyze", "samples/clean_trace.json", "--judge", "not-a-real-provider"])
    assert result.exit_code == 0
    assert "only supports" in result.stdout


def test_compare_clean_before_wasteful_after_is_a_regression():
    result = runner.invoke(app, ["compare", "samples/clean_trace.json", "samples/wasteful_trace.json"])
    assert result.exit_code == 0
    assert "Regressions" in result.stdout
    assert "REGRESSION" in result.stdout


def test_compare_wasteful_before_clean_after_is_resolved_not_regression():
    result = runner.invoke(app, ["compare", "samples/wasteful_trace.json", "samples/clean_trace.json"])
    assert result.exit_code == 0
    assert "Resolved" in result.stdout
    assert "[green]OK" in result.stdout or "OK" in result.stdout


def test_compare_fail_on_regression_flag_exits_nonzero():
    result = runner.invoke(app, [
        "compare", "samples/clean_trace.json", "samples/wasteful_trace.json", "--fail-on-regression",
    ])
    assert result.exit_code == 1


def test_compare_fail_on_regression_flag_exits_zero_on_improvement():
    result = runner.invoke(app, [
        "compare", "samples/wasteful_trace.json", "samples/clean_trace.json", "--fail-on-regression",
    ])
    assert result.exit_code == 0


def test_compare_json_output_written_and_valid(tmp_path):
    out = tmp_path / "cmp.json"
    result = runner.invoke(app, [
        "compare", "samples/wasteful_trace.json", "samples/wasteful_trace_v2.json", "--json", str(out),
    ])
    assert result.exit_code == 0
    data = json.loads(out.read_text())
    assert data["is_regression"] is True
    assert len(data["new_findings"]) == 1
    assert data["new_findings"][0]["tool"] == "read_config"
    assert len(data["resolved_findings"]) == 1


def test_compare_missing_file_exits_2():
    result = runner.invoke(app, ["compare", "samples/does_not_exist.json", "samples/clean_trace.json"])
    assert result.exit_code == 2


import shutil


def _make_trace_dir(tmp_path, files):
    d = tmp_path / "traces"
    d.mkdir()
    for src_name, dest_name in files:
        shutil.copy(f"samples/{src_name}", d / dest_name)
    return d


def test_report_aggregates_across_directory(tmp_path):
    d = _make_trace_dir(tmp_path, [
        ("clean_trace.json", "run1.json"),
        ("wasteful_trace.json", "run2.json"),
    ])
    result = runner.invoke(app, ["report", str(d)])
    assert result.exit_code == 0
    assert "2 trace(s)" in result.stdout
    assert "1 with findings" in result.stdout


def test_report_empty_directory_exits_2(tmp_path):
    d = tmp_path / "empty"
    d.mkdir()
    result = runner.invoke(app, ["report", str(d)])
    assert result.exit_code == 2


def test_report_fail_on_exits_nonzero_when_threshold_met(tmp_path):
    d = _make_trace_dir(tmp_path, [("wasteful_trace.json", "run1.json")])
    result = runner.invoke(app, ["report", str(d), "--fail-on", "medium"])
    assert result.exit_code == 1


def test_report_fail_on_exits_zero_on_all_clean(tmp_path):
    d = _make_trace_dir(tmp_path, [("clean_trace.json", "run1.json")])
    result = runner.invoke(app, ["report", str(d), "--fail-on", "medium"])
    assert result.exit_code == 0


def test_report_json_output_written_and_valid(tmp_path):
    d = _make_trace_dir(tmp_path, [
        ("clean_trace.json", "run1.json"),
        ("wasteful_trace.json", "run2.json"),
    ])
    out = tmp_path / "rollup.json"
    result = runner.invoke(app, ["report", str(d), "--json", str(out)])
    assert result.exit_code == 0
    data = json.loads(out.read_text())
    assert data["trace_count"] == 2
    assert "duplicate_calls" in data["findings_by_check"]


def test_report_top_n_limits_worst_traces(tmp_path):
    d = _make_trace_dir(tmp_path, [
        ("wasteful_trace.json", "run1.json"),
        ("wasteful_trace_v2.json", "run2.json"),
    ])
    out = tmp_path / "rollup.json"
    result = runner.invoke(app, ["report", str(d), "--json", str(out), "--top", "1"])
    assert result.exit_code == 0
    data = json.loads(out.read_text())
    assert len(data["worst_traces"]) == 1
