"""Training command skeletons.

Real training is intentionally not implemented in this simplification pass. The
commands exist so the CLI shape is stable before real image ingestion.
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

app = typer.Typer(help="Training skeleton commands.", no_args_is_help=True)
console = Console()


@app.command("classifier")
def classifier(
    manifest: Path = typer.Option(
        Path("data/images/metadata/image_records.jsonl"),
        help="Accepted local image metadata records.",
    ),
) -> None:
    """Validate the intended training input and stop before training."""
    console.print(f"Training is not implemented. Expected metadata manifest: {manifest}")
    raise typer.Exit(0)


@app.command("detector")
def detector() -> None:
    """Placeholder for a future bird detector training command."""
    console.print("Detector training is not implemented in this scaffold.")
    raise typer.Exit(0)
