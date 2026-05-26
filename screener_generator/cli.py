"""Command-line interface for screener-generator.

    screener-gen generate brief.md                 # rich screener, LLM on by default
    screener-gen generate brief.md --no-llm        # deterministic offline path
    screener-gen generate brief.md --backend gemini
    screener-gen generate brief.md --json-output   # machine-readable, for CI
    screener-gen generate brief.md --markdown       # field-ready markdown doc
    cat brief.md | screener-gen generate -          # read from stdin
    screener-gen batch ./briefs --pattern '*.md'    # JSON array over a folder
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .llm import DEFAULT_BACKEND, available_backends, configured_backends
from .models import SECTION_LABELS, SECTION_ORDER, Disposition, Severity
from .pipeline import build_screener, to_markdown

console = Console()

_SEV_STYLE = {
    Severity.CRITICAL: "bold red",
    Severity.WARNING: "yellow",
    Severity.INFO: "cyan",
}
_DISP_STYLE = {
    Disposition.TERMINATE: "red",
    Disposition.QUOTA: "magenta",
    Disposition.CONTINUE: "green",
}


def _read_brief(path: str | None) -> str:
    if path is None or path == "-":
        data = sys.stdin.read()
    else:
        data = Path(path).read_text(encoding="utf-8")
    if not data.strip():
        raise click.ClickException("Empty brief — provide brief text via a file or stdin.")
    return data


def _emit_rich(screener) -> None:
    spec = screener.spec
    title = spec.product or "Research study"
    header = Text(f"Recruitment screener — {title}", style="bold")
    console.print(Panel(header, border_style="blue", expand=False))

    if screener.summary:
        console.print(Panel(screener.summary, title="Summary", border_style="cyan", expand=False))

    meta = Table.grid(padding=(0, 2))
    meta.add_column(style="dim")
    meta.add_column()
    if screener.quota:
        meta.add_row("Target completes", f"n={screener.quota.total_completes}")
    meta.add_row("Modality", spec.modality.replace("_", " "))
    if screener.incidence_estimate is not None:
        meta.add_row("Est. incidence", f"~{screener.incidence_estimate:.0%}")
    meta.add_row("Questions", str(len(screener.questions)))
    meta.add_row("Terminating", str(screener.terminate_count))
    meta.add_row("Backend", screener.backend or "rule-based (offline)")
    console.print(meta)
    console.print()

    by_section: dict = {}
    for q in screener.questions_in_order():
        by_section.setdefault(q.section, []).append(q)

    for section in SECTION_ORDER:
        qs = by_section.get(section)
        if not qs:
            continue
        console.rule(f"[bold]{SECTION_LABELS[section]}", style="dim")
        for q in qs:
            tag = "·llm" if q.source == "llm" else ""
            console.print(
                Text(f"{q.qid}. ", style="bold blue")
                + Text(q.text)
                + Text(f"  ({q.qtype.value.replace('_', ' ')}){(' ' + tag) if tag else ''}", style="dim")
            )
            for opt in q.options:
                style = _DISP_STYLE.get(opt.disposition, "")
                mark = ""
                if opt.disposition is Disposition.TERMINATE:
                    mark = " ✕ terminate"
                elif opt.disposition is Disposition.QUOTA:
                    mark = f" → {opt.quota_cell}"
                console.print(
                    Text(f"    {opt.code}. ", style="dim") + Text(opt.label) + Text(mark, style=style)
                )
            if q.logic:
                console.print(Text(f"    logic: {q.logic}", style="dim italic"))
            console.print()

    if screener.quota and screener.quota.cells:
        qt = Table(title="Quota plan", title_style="bold", show_edge=False, pad_edge=False)
        qt.add_column("Group", style="dim")
        qt.add_column("Cell")
        qt.add_column("Target", justify="right")
        for c in screener.quota.cells:
            qt.add_row(c.group, c.label, str(c.target))
        console.print(qt)
        for note in screener.quota.notes:
            console.print(Text(f"  note: {note}", style="dim italic"))
        console.print()

    if screener.flags:
        console.rule("[bold]Hygiene flags", style="dim")
        console.print(Text("Probe signals to review before fielding — not verdicts.", style="dim italic"))
        for f in screener.flags:
            where = f" ({f.qid})" if f.qid else ""
            console.print(
                Text(f"  {f.severity.value.upper()}{where}: ", style=_SEV_STYLE.get(f.severity, ""))
                + Text(f.message)
            )


@click.group()
@click.version_option(package_name="screener-generator")
def cli() -> None:
    """Turn a research brief into a fieldwork-ready recruitment screener."""


@cli.command()
@click.argument("brief_path", required=False, type=click.Path())
@click.option("--llm/--no-llm", "use_llm", default=True, help="Use LLM enrichment (default on).")
@click.option(
    "--backend",
    type=click.Choice(available_backends()),
    default=DEFAULT_BACKEND,
    show_default=True,
    help="LLM backend to use when enrichment is on.",
)
@click.option("--json-output", "json_output", is_flag=True, help="Emit JSON instead of a table.")
@click.option("--markdown", "as_markdown", is_flag=True, help="Emit a field-ready markdown screener.")
def generate(brief_path, use_llm, backend, json_output, as_markdown) -> None:
    """Generate a screener from a BRIEF_PATH file (or stdin with '-')."""
    brief = _read_brief(brief_path)
    warnings: list[str] = []
    screener = build_screener(brief, use_llm=use_llm, backend=backend, on_warning=warnings.append)

    if json_output:
        click.echo(json.dumps(screener.to_dict(), indent=2))
        return
    if as_markdown:
        click.echo(to_markdown(screener))
        return

    for w in warnings:
        console.print(f"[yellow]warning:[/yellow] {w}", highlight=False)
    _emit_rich(screener)


@cli.command()
@click.argument("directory", type=click.Path(exists=True, file_okay=False))
@click.option("--llm/--no-llm", "use_llm", default=True, help="Use LLM enrichment (default on).")
@click.option("--backend", type=click.Choice(available_backends()), default=DEFAULT_BACKEND, show_default=True)
@click.option("--pattern", default="*.md", show_default=True, help="Glob for brief files.")
def batch(directory, use_llm, backend, pattern) -> None:
    """Generate a screener for every brief in DIRECTORY; emit a JSON array."""
    results = []
    for path in sorted(Path(directory).glob(pattern)):
        screener = build_screener(path.read_text(encoding="utf-8"), use_llm=use_llm, backend=backend)
        results.append({"file": path.name, **screener.to_dict()})
    click.echo(json.dumps(results, indent=2))


@cli.command()
def backends() -> None:
    """List known LLM backends and which ones have API keys configured."""
    configured = set(configured_backends())
    for name in available_backends():
        status = "[green]configured[/green]" if name in configured else "[dim]no key[/dim]"
        console.print(f"  {name:<10} {status}")


if __name__ == "__main__":
    cli()
