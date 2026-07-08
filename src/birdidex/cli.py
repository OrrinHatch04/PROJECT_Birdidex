"""CLI entry point for the bird scanner.

All commands are offline by default. Live provider requests are gated behind an
explicit ``--live`` flag and configured tokens, and are intentionally not implemented
as network calls in this MVP.
"""

from __future__ import annotations

from pathlib import Path

import typer
from bird_core.paths import get_configs_dir
from rich.console import Console

app = typer.Typer(help="Bird Scanner — score ROI species evidence (offline by default).")
console = Console()


@app.command()
def candidates(
    scoring_config: str = typer.Option(
        "configs/scanner/scoring.yaml", help="Scoring weights/thresholds YAML"
    ),
    year: int = typer.Option(2025, help="Reference year for recency scoring"),
) -> None:
    """Run the ROI species-candidate scan (dry-run, deterministic seed list)."""
    from bird_roi_scan.pipeline import run_candidate_scan

    cfg = Path(scoring_config)
    if not cfg.is_absolute():
        cfg = get_configs_dir().parent / scoring_config
    result = run_candidate_scan(scoring_config=cfg if cfg.exists() else None, current_year=year)
    console.print(f"[green]Scored {len(result.scored)} species.[/]")
    console.print(f"  candidates: {result.candidates_csv}")
    console.print(f"  tiers:      {result.tiers_csv}")
    console.print(f"  report:     {result.report_md}")


@app.command()
def score() -> None:
    """Alias for `candidates` (kept for backwards compatibility)."""
    candidates()


@app.command("pull-occurrences")
def pull_occurrences(
    live: bool = typer.Option(
        False, "--live", help="Perform real provider requests (not implemented)"
    ),
) -> None:
    """Explicit provider occurrence request command (disabled unless --live)."""
    if not live:
        console.print(
            "[yellow]Dry-run:[/] no provider requests made. "
            "Pass --live with configured tokens to enable (not implemented in this MVP)."
        )
        raise typer.Exit(0)
    console.print("[red]Live provider requests are not implemented in this MVP.[/]")
    raise typer.Exit(1)


if __name__ == "__main__":
    app()
