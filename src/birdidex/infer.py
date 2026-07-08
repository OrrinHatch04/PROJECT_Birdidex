"""Inference command skeletons."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import typer
from rich.console import Console

app = typer.Typer(help="Inference skeleton commands.", no_args_is_help=True)
console = Console()


@dataclass(frozen=True)
class Prediction:
    class_id: int | None
    label: str
    confidence: float


@dataclass(frozen=True)
class ConfidenceGateDecision:
    status: str
    accept: bool
    reason: str
    top_prediction: Prediction | None


def _as_prediction(item: Prediction | dict[str, Any]) -> Prediction:
    if isinstance(item, Prediction):
        return item
    return Prediction(
        class_id=item.get("class_id"),
        label=str(item.get("label") or item.get("predicted_label") or ""),
        confidence=float(item.get("confidence") or item.get("score") or 0.0),
    )


def confidence_gate(
    top_k_predictions: list[Prediction | dict[str, Any]],
    *,
    image_quality_score: float | None = None,
    high_threshold: float = 0.85,
    medium_threshold: float = 0.60,
    margin_threshold: float = 0.15,
    min_quality_score: float = 8.0,
    multi_subject: bool = False,
) -> ConfidenceGateDecision:
    """Convert visual top-k scores into an abstention-aware field decision.

    The gate is deliberately conservative for field use: context priors may re-rank
    nearby classes, but they should not force an ID when visual evidence is weak.
    """
    predictions = [_as_prediction(item) for item in top_k_predictions]
    predictions.sort(key=lambda pred: pred.confidence, reverse=True)

    if multi_subject:
        return ConfidenceGateDecision(
            status="multi-subject",
            accept=False,
            reason="multiple subjects detected; crop or review before assigning one species",
            top_prediction=predictions[0] if predictions else None,
        )
    if not predictions:
        return ConfidenceGateDecision(
            status="out-of-set",
            accept=False,
            reason="no classifier predictions were supplied",
            top_prediction=None,
        )

    top = predictions[0]
    label = top.label.strip().lower()
    if top.class_id is None or label in {"", "unknown", "out_of_set", "out-of-set", "background"}:
        return ConfidenceGateDecision(
            status="out-of-set",
            accept=False,
            reason="top prediction is not a known classifier class",
            top_prediction=top,
        )

    if image_quality_score is not None and image_quality_score < min_quality_score:
        return ConfidenceGateDecision(
            status="low confidence",
            accept=False,
            reason="image quality score is below the confidence gate",
            top_prediction=top,
        )

    runner_up = predictions[1].confidence if len(predictions) > 1 else 0.0
    margin = top.confidence - runner_up
    if top.confidence >= high_threshold and margin >= margin_threshold:
        return ConfidenceGateDecision(
            status="high confidence",
            accept=True,
            reason="top prediction is strong and separated from the runner-up",
            top_prediction=top,
        )
    if top.confidence >= medium_threshold:
        return ConfidenceGateDecision(
            status="medium confidence",
            accept=False,
            reason="candidate is plausible but should be confirmed by the user",
            top_prediction=top,
        )
    return ConfidenceGateDecision(
        status="low confidence",
        accept=False,
        reason="classifier confidence is too low for an automatic ID",
        top_prediction=top,
    )


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
