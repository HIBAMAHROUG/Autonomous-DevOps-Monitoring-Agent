from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from typing import Dict

import numpy as np
import pandas as pd

from .base import DataSource, Sample
from ..config import settings


class MockDataSource(DataSource):
    def __init__(self, anomaly_probability: float = 0.03, seed: int = 42):
        self.anomaly_probability = anomaly_probability
        self.rng = np.random.default_rng(seed)

    def _generate_sample(self) -> Sample:
        is_anomaly = bool(self.rng.random() < self.anomaly_probability)
        cpu = float(self.rng.normal(35 if not is_anomaly else 92, 4 if not is_anomaly else 5))
        memory = float(self.rng.normal(55 if not is_anomaly else 90, 3 if not is_anomaly else 4))
        network = float(self.rng.normal(25 if not is_anomaly else 90, 2 if not is_anomaly else 5))
        disk = float(self.rng.normal(10 if not is_anomaly else 94, 1 if not is_anomaly else 3))
        values = {
            "cpu_usage": max(0.0, min(100.0, cpu)),
            "memory_usage": max(0.0, min(100.0, memory)),
            "network_usage": max(0.0, network),
            "disk_usage": max(0.0, min(100.0, disk)),
        }
        return Sample(timestamp=datetime.now(timezone.utc), values=values, is_anomaly=is_anomaly)

    def fetch_latest(self) -> Sample:
        return self._generate_sample()

    def fetch_history(self, days: int = 7):
        points = max(10, days * 24 * 2)
        rows = []
        current = datetime.now(timezone.utc) - timedelta(days=days)
        step = timedelta(minutes=30)
        for _ in range(points):
            sample = self._generate_sample()
            row = {"timestamp": current, **sample.values, "is_anomaly": sample.is_anomaly}
            rows.append(row)
            current += step
        return pd.DataFrame(rows)
