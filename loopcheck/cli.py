"""
loopcheck -- zero-instrumentation waste auditor for hand-rolled agent loops.

  loopcheck analyze trace.json
  loopcheck analyze trace.json --json report.json --fail-on medium
  loopcheck analyze trace.json --judge groq   # needs GROQ_API_KEY

v0.1: trace schema + duplicate_calls + loop_thrash checks, text/JSON report, CI-gate exit code.
v0.2: record traces directly from OpenAI/Anthropic/Groq loops (adapters), not just hand-written JSON.
v0.3: parallel tool-call support (record_*_turn).
v0.4: --judge for the semantic_redundancy check against a live model. <- current
See CHANGELOG.md.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from loopcheck import __version__
from loopcheck.checks.duplicate_calls import check_duplicate_calls
from loopcheck.checks.loop_thrash import check_loop_thrash
from loopcheck.checks.semantic_redundancy import check_semantic_redundancy
from loopcheck.findings import Finding, Severity
from loopcheck.report import render_text, to_json
from loopcheck.trace import Trace

app = typer.Typer(
    name="loopcheck",
    help="[bold cyan]loopcheck[/] -- zero-instrumentation waste auditor for AI agent loops.",
    rich_markup_mode="rich",
    no_args_is_help=True,
)
console = Console()


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"loopcheck {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(False, "--version", callback=_version_callback, is_eager=True),
) -> None:
    pass


def run_checks(trace: Trace) -> list[Finding]:
    findings: list[Finding] = []
    findings += check_duplicate_calls(trace)
    findings += check_loop_thrash(trace)
    return findings


@app.command()
def analyze(
    trace_file: Path = typer.Argument(..., help="Path to a loopcheck trace JSON file."),
    json_out: Optional[Path] = typer.Option(None, "--json", help="Write JSON report to this path"),
    fail_on: Optional[str] = typer.Option(
        None, "--fail-on", help="Exit 1 if any finding at/above this severity (info|low|medium|high). For CI gates."
    ),
    judge: Optional[str] = typer.Option(
        None, "--judge", help="Also run the semantic_redundancy check against a live model "
                              "(currently: groq, needs GROQ_API_KEY)."
    ),
    judge_model: str = typer.Option(
        "openai/gpt-oss-120b", "--judge-model", help="Model for --judge groq."
    ),
    max_judge_pairs: int = typer.Option(
        20, "--max-judge-pairs", help="Cap on how many same-tool call pairs --judge will compare."
    ),
):
    """Analyze a single agent trace for wasted tool calls."""
    try:
        trace = Trace.load(trace_file)
    except Exception as exc:  # noqa: BLE001
        console.print(f"[red]Could not read trace file:[/] {exc}")
        raise typer.Exit(2)

    findings = run_checks(trace)

    if judge:
        findings += asyncio.run(_run_judge_check(trace, judge, judge_model, max_judge_pairs))

    console.print(render_text(trace, findings))

    if json_out:
        json_out.write_text(to_json(trace, findings), encoding="utf-8")
        console.print(f"\n[dim]JSON report written to {json_out}[/]")

    if fail_on:
        order = ["info", "low", "medium", "high"]
        threshold = order.index(fail_on.lower())
        if any(order.index(f.severity.value) >= threshold for f in findings):
            raise typer.Exit(1)


async def _run_judge_check(trace: Trace, judge_name: str, judge_model: str, max_pairs: int) -> list[Finding]:
    import os

    if judge_name != "groq":
        console.print(f"[yellow]--judge currently only supports 'groq', got '{judge_name}'[/]")
        return []

    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        console.print("[yellow]--judge groq needs GROQ_API_KEY set -- skipping semantic_redundancy check.[/]")
        return []

    from loopcheck.judges.groq_judge import GroqJudge
    judge = GroqJudge(api_key=api_key, model=judge_model)

    console.print("[dim]running semantic_redundancy check against a live model...[/]")
    return await check_semantic_redundancy(trace, judge, max_pairs=max_pairs)


if __name__ == "__main__":
    app()
