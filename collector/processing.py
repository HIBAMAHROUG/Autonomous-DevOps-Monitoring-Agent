from __future__ import annotations

import os
from statistics import mean
from typing import Dict, Iterable, List


NETWORK_MAX_BYTES_PER_SECOND = float(os.getenv("NETWORK_MAX_BYTES_PER_SECOND", "10485760"))


def _clamp(value: float, minimum: float = 0.0, maximum: float = 100.0) -> float:
    return max(minimum, min(maximum, value))


def normalize_metrics(metrics: Dict[str, float]) -> Dict[str, float]:
    network_baseline = NETWORK_MAX_BYTES_PER_SECOND if NETWORK_MAX_BYTES_PER_SECOND > 0 else 1.0
    return {
        "cpu_usage": _clamp(metrics.get("cpu_usage", 0.0)),
        "memory_usage": _clamp(metrics.get("memory_usage", 0.0)),
        "network_usage": _clamp((metrics.get("network_usage", 0.0) / network_baseline) * 100.0),
        "disk_usage": _clamp(metrics.get("disk_usage", 0.0)),
    }


def aggregate_metrics(samples: Iterable[Dict[str, float]]) -> Dict[str, Dict[str, float]]:
    values: Dict[str, List[float]] = {}
    for sample in samples:
        for key, value in sample.items():
            try:
                values.setdefault(key, []).append(float(value))
            except (TypeError, ValueError):
                continue

    aggregates: Dict[str, Dict[str, float]] = {}
    for key, series in values.items():
        if not series:
            continue
        aggregates[key] = {
            "count": float(len(series)),
            "min": min(series),
            "max": max(series),
            "mean": mean(series),
        }
    return aggregates
