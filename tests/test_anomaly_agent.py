from pathlib import Path

from anomaly_agent.alerting import Alert
from anomaly_agent.config import settings
from anomaly_agent.datasources.mock import MockDataSource
from anomaly_agent.explain import explain
from anomaly_agent.features import FeatureStore, MetricBaseline
from anomaly_agent.model import AnomalyDetector, Thresholds
from anomaly_agent.severity import classify_severity


def test_metric_baseline_and_feature_store_build_z_scores():
    store = FeatureStore(metric_names=["cpu_usage", "memory_usage"], window_size=3, ewma_alpha=0.5)

    first = store.observe({"cpu_usage": 10.0, "memory_usage": 20.0})
    second = store.observe({"cpu_usage": 14.0, "memory_usage": 18.0})

    assert set(first) == {"cpu_usage", "memory_usage"}
    assert set(second) == {"cpu_usage", "memory_usage"}
    assert store.baselines["cpu_usage"].ewma_mean is not None
    assert store.baselines["cpu_usage"].std > 0


def test_severity_classification_boundaries():
    thresholds = Thresholds(anomaly=1.0, medium=2.0, high=3.0, critical=4.0)

    assert classify_severity(0.5, thresholds) is None
    assert classify_severity(1.0, thresholds) == "low"
    assert classify_severity(2.2, thresholds) == "medium"
    assert classify_severity(3.2, thresholds) == "high"
    assert classify_severity(4.2, thresholds) == "critical"


def test_explain_returns_narrative_with_top_contributors():
    store = FeatureStore(metric_names=["cpu_usage", "memory_usage"], window_size=3, ewma_alpha=0.5)
    store.observe({"cpu_usage": 10.0, "memory_usage": 20.0})
    store.observe({"cpu_usage": 11.0, "memory_usage": 19.0})

    result = explain(
        sample={"cpu_usage": 30.0, "memory_usage": 22.0},
        z_scores={"cpu_usage": 5.0, "memory_usage": 0.5},
        feature_store=store,
        top_k=1,
    )

    assert result["top_contributors"]
    assert "cpu_usage" in result["narrative"]


def test_detector_fit_save_and_load_roundtrip(tmp_path: Path):
    source = MockDataSource(anomaly_probability=0.03, seed=7)
    history = source.fetch_history(days=2)

    detector = AnomalyDetector()
    detector.fit(history)
    model_path = tmp_path / "anomaly_model.joblib"
    detector.save(str(model_path))

    loaded = AnomalyDetector.load(str(model_path))

    assert loaded.metric_names == detector.metric_names
    assert loaded.thresholds.to_dict() == detector.thresholds.to_dict()
    score, z_scores = loaded.score_sample({"cpu_usage": 35.0, "memory_usage": 55.0, "network_usage": 25.0, "disk_usage": 10.0})
    assert isinstance(score, float)
    assert set(z_scores) == set(loaded.metric_names)


def test_mock_source_and_alert_creation():
    sample = MockDataSource(seed=1).fetch_latest()
    alert = Alert.create(
        severity="low",
        score=1.23,
        sample=sample.values,
        explanation={"narrative": "test"},
        sample_timestamp=sample.timestamp,
    )

    assert alert.severity == "low"
    assert alert.score == 1.23
    assert alert.detection_latency_seconds >= 0
