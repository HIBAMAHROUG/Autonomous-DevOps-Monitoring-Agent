"""
Modèle de détection d'anomalies.

Approche hybride, choisie pour répondre à 3 critères d'acceptation à la fois :
  - "Modèle entraîné"        -> IsolationForest multivarié (scikit-learn)
  - "Explainability"         -> features = z-scores par métrique (lisibles)
  - "Classification sévérité"-> seuils calibrés sur la distribution des scores

Le modèle consomme des z-scores (pas les valeurs brutes) : il est donc
indépendant de l'échelle de chaque métrique (% vs Mbps vs ops/s).
"""
import os
from dataclasses import dataclass
from typing import Dict, List, Tuple

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

from .config import settings
from .features import FeatureStore


@dataclass
class Thresholds:
    anomaly: float
    medium: float
    high: float
    critical: float

    def to_dict(self):
        return self.__dict__

    @staticmethod
    def from_dict(d):
        return Thresholds(**d)


class AnomalyDetector:
    def __init__(self, metric_names: List[str] = None):
        self.metric_names = metric_names or settings.metrics
        self.feature_store = FeatureStore(
            metric_names=self.metric_names,
            window_size=settings.rolling_window_size,
            ewma_alpha=settings.ewma_alpha,
        )
        self.model: IsolationForest = None
        self.thresholds: Thresholds = None

    def _build_feature_matrix(self, df: pd.DataFrame) -> np.ndarray:
        rows = []
        for _, row in df.iterrows():
            sample = {m: row[m] for m in self.metric_names if m in row}
            z = self.feature_store.observe(sample)
            rows.append(self.feature_store.feature_vector(z))
        return np.vstack(rows)

    def fit(self, history_df: pd.DataFrame, calibration_fraction: float = 0.2) -> None:
        history_df = history_df.sort_values("timestamp").reset_index(drop=True)
        split_idx = int(len(history_df) * (1 - calibration_fraction))
        train_df, calib_df = history_df.iloc[:split_idx], history_df.iloc[split_idx:]

        X_train = self._build_feature_matrix(train_df)
        self.model = IsolationForest(
            n_estimators=settings.isolation_forest_estimators,
            contamination=settings.isolation_forest_contamination,
            random_state=settings.random_state,
        )
        self.model.fit(X_train)

        X_calib = self._build_feature_matrix(calib_df)
        calib_scores = -self.model.score_samples(X_calib)
        self.thresholds = self._calibrate_thresholds(calib_scores)

    def _calibrate_thresholds(self, normal_scores: np.ndarray) -> Thresholds:
        fpr = settings.target_false_positive_rate
        anomaly_th = float(np.percentile(normal_scores, 100 * (1 - fpr)))
        medium_th = float(np.percentile(normal_scores, 100 * (1 - fpr / 2)))
        high_th = float(np.percentile(normal_scores, 99.5))
        critical_th = float(np.percentile(normal_scores, 99.9))
        medium_th = max(medium_th, anomaly_th * 1.001)
        high_th = max(high_th, medium_th * 1.001)
        critical_th = max(critical_th, high_th * 1.001)
        return Thresholds(anomaly=anomaly_th, medium=medium_th, high=high_th, critical=critical_th)

    def score_sample(self, sample: Dict[str, float]) -> Tuple[float, Dict[str, float]]:
        z_scores = self.feature_store.observe(sample)
        vec = self.feature_store.feature_vector(z_scores).reshape(1, -1)
        score = float(-self.model.score_samples(vec)[0])
        return score, z_scores

    def save(self, path: str = None) -> str:
        path = path or settings.model_artifact_path
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        joblib.dump({
            "model": self.model,
            "metric_names": self.metric_names,
            "thresholds": self.thresholds.to_dict(),
            "feature_store_state": self.feature_store.state_dict(),
            "config_snapshot": {
                "rolling_window_size": settings.rolling_window_size,
                "ewma_alpha": settings.ewma_alpha,
            },
        }, path)
        return path

    @staticmethod
    def load(path: str = None) -> "AnomalyDetector":
        path = path or settings.model_artifact_path
        if not os.path.exists(path):
            from .datasources.mock import MockDataSource

            bootstrap_source = MockDataSource(anomaly_probability=0.03, seed=42)
            bootstrap_history = bootstrap_source.fetch_history(days=30)
            detector = AnomalyDetector()
            detector.fit(bootstrap_history)
            detector.save(path)
            return detector

        payload = joblib.load(path)
        detector = AnomalyDetector(metric_names=payload["metric_names"])
        detector.model = payload["model"]
        detector.thresholds = Thresholds.from_dict(payload["thresholds"])
        detector.feature_store.load_state_dict(payload["feature_store_state"])
        return detector
