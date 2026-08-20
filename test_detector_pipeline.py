from datetime import datetime, timedelta, timezone

from anomaly_agent.model import Thresholds
from detector.pipeline import check_and_confirm


class FakeMLDetector:
    """Détecteur ML factice : score fixe, injectable dans les tests."""

    def __init__(self, score: float, thresholds: Thresholds):
        self._score = score
        self.thresholds = thresholds
        self.calls = 0

    def score_sample(self, sample):
        self.calls += 1
        return self._score, {k: 0.0 for k in sample}


THRESHOLDS = Thresholds(
    anomaly=1.0,
    medium=2.0,
    high=3.0,
    critical=4.0,
)


def make_metrics(cpu=95, memory=40):
    return {
        "cpu_usage": cpu,
        "memory_usage": memory,
        "network_usage": 100,
        "disk_usage": 50,
    }


def test_no_ml_call_when_threshold_prefilter_does_not_fire():
    ml = FakeMLDetector(
        score=5.0,
        thresholds=THRESHOLDS,
    )

    alerts = check_and_confirm(
        make_metrics(cpu=10),
        service="svc-a",
        ml_detector=ml,
    )

    assert alerts == []
    assert ml.calls == 0


def test_threshold_sustained_but_ml_does_not_confirm_no_alert():
    from detector.detector import _default_detector

    now = datetime(
        2026,
        1,
        1,
        tzinfo=timezone.utc,
    )

    metrics = make_metrics(cpu=95)

    # Simule un dépassement déjà soutenu depuis 300s pour ce service.
    _default_detector._breach_since[
        ("svc-b", "cpu")
    ] = now - timedelta(seconds=300)

    ml = FakeMLDetector(
        score=0.1,
        thresholds=THRESHOLDS,
    )

    alerts = check_and_confirm(
        metrics,
        service="svc-b",
        ml_detector=ml,
    )

    assert alerts == []
    assert ml.calls == 1


def test_threshold_and_ml_both_confirm_produces_enriched_alert():
    from detector.detector import _default_detector

    now = datetime(
        2026,
        1,
        1,
        tzinfo=timezone.utc,
    )

    metrics = make_metrics(cpu=95)

    _default_detector._breach_since[
        ("svc-c", "cpu")
    ] = now - timedelta(seconds=300)

    ml = FakeMLDetector(
        score=4.5,
        thresholds=THRESHOLDS,
    )

    alerts = check_and_confirm(
        metrics,
        service="svc-c",
        ml_detector=ml,
    )

    assert len(alerts) == 1
    assert alerts[0]["severity"] == "critical"
    assert alerts[0]["ml_score"] == 4.5
    assert "z_scores" in alerts[0]
    assert alerts[0]["service"] == "svc-c"
