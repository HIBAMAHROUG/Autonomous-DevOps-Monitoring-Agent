"""
Baseline statistique par métrique (moyenne/écart-type glissants + EWMA).
Sert à la fois de :
  1) source des z-scores (utilisés pour l'explainability),
  2) générateur de features pour le modèle multivarié (IsolationForest).
"""
from collections import deque
from dataclasses import dataclass, field
from typing import Dict, List

import numpy as np


@dataclass
class MetricBaseline:
    window_size: int
    ewma_alpha: float
    values: deque = field(default_factory=deque)
    ewma_mean: float = None
    ewma_var: float = None

    def update(self, x: float) -> None:
        self.values.append(x)
        if len(self.values) > self.window_size:
            self.values.popleft()

        if self.ewma_mean is None:
            self.ewma_mean = x
            self.ewma_var = 0.0
        else:
            diff = x - self.ewma_mean
            incr = self.ewma_alpha * diff
            self.ewma_mean += incr
            self.ewma_var = (1 - self.ewma_alpha) * (self.ewma_var + self.ewma_alpha * diff * diff)

    @property
    def std(self) -> float:
        return max(self.ewma_var ** 0.5, 1e-6) if self.ewma_var is not None else 1e-6

    def z_score(self, x: float) -> float:
        if self.ewma_mean is None:
            return 0.0
        return (x - self.ewma_mean) / self.std


class FeatureStore:
    """Maintient une MetricBaseline par métrique et calcule le vecteur de features."""

    def __init__(self, metric_names: List[str], window_size: int, ewma_alpha: float):
        self.metric_names = metric_names
        self.baselines: Dict[str, MetricBaseline] = {
            m: MetricBaseline(window_size=window_size, ewma_alpha=ewma_alpha) for m in metric_names
        }

    def observe(self, sample: Dict[str, float]) -> Dict[str, float]:
        """Ingère un point et retourne les z-scores AVANT mise à jour (pour scorer le point courant)."""
        z_scores = {}
        for m in self.metric_names:
            if m not in sample:
                z_scores[m] = 0.0
                continue
            baseline = self.baselines[m]
            z_scores[m] = baseline.z_score(sample[m])
            baseline.update(sample[m])
        return z_scores

    def feature_vector(self, z_scores: Dict[str, float]) -> np.ndarray:
        return np.array([z_scores.get(m, 0.0) for m in self.metric_names], dtype=float)

    def state_dict(self):
        return {
            m: {
                "values": list(b.values),
                "ewma_mean": b.ewma_mean,
                "ewma_var": b.ewma_var,
            } for m, b in self.baselines.items()
        }

    def load_state_dict(self, state):
        for m, s in state.items():
            b = self.baselines[m]
            b.values = deque(s["values"], maxlen=None)
            b.ewma_mean = s["ewma_mean"]
            b.ewma_var = s["ewma_var"]
