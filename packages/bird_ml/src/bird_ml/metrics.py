"""Classification metrics helpers (numpy-only, no scikit-learn dependency).

These operate on raw score matrices (``scores[n, c]``) and integer label vectors so
they can be reused by both the training evaluator and offline tests without pulling in
torch or scikit-learn.
"""

from __future__ import annotations

import numpy as np


def top_k_accuracy(scores: np.ndarray, labels: np.ndarray, k: int = 5) -> float:
    """Fraction of samples where the true label appears in the top-k predictions."""
    k = min(k, scores.shape[1])
    top_k = np.argsort(scores, axis=1)[:, -k:]
    correct = np.any(top_k == labels[:, None], axis=1)
    return float(correct.mean())


def confusion_matrix(labels: np.ndarray, preds: np.ndarray, num_classes: int) -> np.ndarray:
    """Return an ``[num_classes, num_classes]`` confusion matrix (rows=true, cols=pred)."""
    cm = np.zeros((num_classes, num_classes), dtype=np.int64)
    for t, p in zip(labels.tolist(), preds.tolist(), strict=True):
        cm[int(t), int(p)] += 1
    return cm


def per_class_prf(
    labels: np.ndarray, preds: np.ndarray, num_classes: int
) -> dict[int, dict[str, float]]:
    """Per-class precision, recall, F1, and support."""
    cm = confusion_matrix(labels, preds, num_classes)
    out: dict[int, dict[str, float]] = {}
    for c in range(num_classes):
        tp = int(cm[c, c])
        fp = int(cm[:, c].sum() - tp)
        fn = int(cm[c, :].sum() - tp)
        support = int(cm[c, :].sum())
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = (
            2 * precision * recall / (precision + recall)
            if (precision + recall)
            else 0.0
        )
        out[c] = {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "support": float(support),
        }
    return out


def weighted_f1(labels: np.ndarray, preds: np.ndarray, num_classes: int) -> float:
    """Support-weighted mean F1 across classes."""
    prf = per_class_prf(labels, preds, num_classes)
    total = sum(v["support"] for v in prf.values())
    if total == 0:
        return 0.0
    return float(sum(v["f1"] * v["support"] for v in prf.values()) / total)
