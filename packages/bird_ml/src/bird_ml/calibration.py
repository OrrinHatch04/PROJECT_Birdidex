"""Post-hoc calibration helpers (temperature scaling placeholder).

TODO: Implement temperature scaling using a held-out calibration split.
TODO: Expose calibrated_proba() that rescales raw logits before returning to UI.
"""

from __future__ import annotations

import numpy as np


class TemperatureScaler:
    """Divides raw logits by a scalar temperature before softmax."""

    def __init__(self, temperature: float = 1.0) -> None:
        if temperature <= 0:
            raise ValueError("temperature must be positive")
        self.temperature = temperature

    def calibrate(self, logits: np.ndarray) -> np.ndarray:
        """Return softmax probabilities after temperature scaling."""
        scaled = logits / self.temperature
        exp = np.exp(scaled - scaled.max(axis=-1, keepdims=True))
        return exp / exp.sum(axis=-1, keepdims=True)
