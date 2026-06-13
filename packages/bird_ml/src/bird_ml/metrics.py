"""Classification metrics helpers.

TODO: Add per-class precision/recall/F1 summary tables.
TODO: Integrate confusion matrix export for mlflow logging.
"""

from __future__ import annotations

import numpy as np


def top_k_accuracy(scores: np.ndarray, labels: np.ndarray, k: int = 5) -> float:
    """Fraction of samples where the true label appears in the top-k predictions."""
    top_k = np.argsort(scores, axis=1)[:, -k:]
    correct = np.any(top_k == labels[:, None], axis=1)
    return float(correct.mean())
