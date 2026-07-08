"""Inference command skeletons."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

app = typer.Typer(help="Inference skeleton commands.", no_args_is_help=True)
console = Console()


@app.command("image")
def image(
    path: Path = typer.Argument(..., help="Image path for a future inference run."),
) -> None:
    """Stop before real inference; the model/runtime are not implemented here."""
    console.print(f"Inference is not implemented. Received image path: {path}")
    raise typer.Exit(0)


@app.command("doctor")
def doctor() -> None:
    """Print the current inference scaffold status."""
    console.print("Inference scaffold is installed. No model runtime is configured.")
