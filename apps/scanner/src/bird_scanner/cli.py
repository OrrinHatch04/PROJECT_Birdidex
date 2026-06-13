"""CLI entry point for the bird scanner."""

from __future__ import annotations

import typer
from rich.console import Console

app = typer.Typer(help="Bird Scanner — collect and score ROI species evidence.")
console = Console()


@app.command()
def score(
    config: str = typer.Option("configs/scanner/providers.yaml", help="Providers config path"),
) -> None:
    """Score species evidence for ROI inclusion.

    TODO: Wire up pipeline.run_scan() and persist results to data/processed/.
    """
    console.print("[bold yellow]score[/] — not yet implemented")


@app.command()
def report(
    output: str = typer.Option("data/reports/species_report.csv", help="Output CSV path"),
) -> None:
    """Generate a CSV/markdown evidence report.

    TODO: Load scored species from DuckDB and write report.
    """
    console.print("[bold yellow]report[/] — not yet implemented")


if __name__ == "__main__":
    app()
