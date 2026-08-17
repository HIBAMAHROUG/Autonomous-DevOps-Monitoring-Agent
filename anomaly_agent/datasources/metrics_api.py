from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict

import pandas as pd
import requests

from .base import DataSource, Sample
from ..config import settings


class MetricsApiDataSource(DataSource):
    def __init__(self, base_url: str = None):
        self.base_url = base_url or settings.metrics_api_url

    def fetch_latest(self) -> Sample:
        response = requests.get(self.base_url, timeout=10)
        response.raise_for_status()
        payload = response.json()
        timestamp = payload.get("timestamp")
        values = payload.get("raw") or payload.get("normalized") or payload
        parsed = datetime.fromisoformat(timestamp) if timestamp else datetime.now(timezone.utc)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return Sample(timestamp=parsed, values={k: float(v) for k, v in values.items()})

    def fetch_history(self, days: int = 7):
        window = f"{days}d"
        response = requests.get(f"{self.base_url.rsplit('/', 1)[0]}/history", params={"window": window, "limit": 5000}, timeout=10)
        response.raise_for_status()
        payload = response.json()
        rows = []
        for item in payload:
            rows.append({"timestamp": item["timestamp"], **item.get("raw", {}), "is_anomaly": False})
        return pd.DataFrame(rows)
