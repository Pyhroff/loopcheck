"""--fail-on is validated before any trace is read."""
from pathlib import Path

from typer.testing import CliRunner

from loopcheck.cli import app

runner = CliRunner()
SAMPLES = Path(__file__).resolve().parent.parent / "samples"


def test_analyze_rejects_unknown_fail_on_without_traceback(tmp_path):
    out = tmp_path / "report.json"
    result = runner.invoke(app, ["analyze", str(SAMPLES / "wasteful_trace.json"), "--fail-on", "hgih", "--json", str(out)])
    assert result.exit_code == 2
    assert not isinstance(result.exception, ValueError)
    assert not out.exists()


def test_report_rejects_unknown_fail_on_without_traceback():
    result = runner.invoke(app, ["report", str(SAMPLES), "--fail-on", "critical"])
    assert result.exit_code == 2
    assert not isinstance(result.exception, ValueError)


def test_valid_fail_on_still_gates():
    result = runner.invoke(app, ["analyze", str(SAMPLES / "wasteful_trace.json"), "--fail-on", "low"])
    assert result.exit_code == 1
    result = runner.invoke(app, ["analyze", str(SAMPLES / "clean_trace.json"), "--fail-on", "low"])
    assert result.exit_code == 0
