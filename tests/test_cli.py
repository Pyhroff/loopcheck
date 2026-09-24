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
    assert "0.4.0" in result.stdout


def test_judge_flag_without_api_key_skips_gracefully(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    result = runner.invoke(app, ["analyze", "samples/clean_trace.json", "--judge", "groq"])
    assert result.exit_code == 0
    assert "GROQ_API_KEY" in result.stdout


def test_judge_flag_with_unsupported_provider_skips_gracefully():
    result = runner.invoke(app, ["analyze", "samples/clean_trace.json", "--judge", "not-a-real-provider"])
    assert result.exit_code == 0
    assert "only supports" in result.stdout
