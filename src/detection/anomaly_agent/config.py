from dataclasses import dataclass
import os
from typing import List


@dataclass(frozen=True)
class Settings:
    metrics: List[str] = ("cpu_usage", "memory_usage", "network_usage", "disk_usage")
    rolling_window_size: int = 120
    ewma_alpha: float = 0.2
    isolation_forest_estimators: int = 200
    isolation_forest_contamination: float = 0.03
    random_state: int = 42
    target_false_positive_rate: float = 0.05
    max_detection_latency_seconds: float = 60.0
    collection_interval_seconds: int = 30
    model_artifact_path: str = "artifacts/anomaly_model.joblib"
    alert_webhook_url: str = os.getenv("ALERT_WEBHOOK_URL", "") or ""
    data_source: str = os.getenv("ANOMALY_DATA_SOURCE", "mock")
    metrics_api_url: str = os.getenv("METRICS_API_URL", "http://localhost:5000/api/metrics/latest")


settings = Settings()
