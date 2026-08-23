from datetime import datetime, timedelta, timezone

from detector.detector import AnomalyDetector

RULES = {
    "cpu": {"threshold": 90, "duration": 300, "trend_multiplier": 1.5},
    "memory": {"threshold": 85, "duration": 300, "trend_multiplier": 1.5},
    "maintenance_windows": [],
}


def make_detector():
    return AnomalyDetector(rules=dict(RULES))


def test_no_alert_below_threshold():
    detector = make_detector()
    alerts = detector.check({"cpu_usage": 50, "memory_usage": 40}, service="svc-a")
    assert alerts == []


def test_no_alert_if_breach_not_sustained_long_enough():
    detector = make_detector()
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)

    alerts = detector.check({"cpu_usage": 95, "memory_usage": 40}, service="svc-a", now=t0)
    assert alerts == []  # premier dépassement, pas encore soutenu

    alerts = detector.check(
        {"cpu_usage": 95, "memory_usage": 40}, service="svc-a", now=t0 + timedelta(seconds=60)
    )
    assert alerts == []  # 60s < duration (300s)


def test_alert_when_breach_sustained_past_duration():
    detector = make_detector()
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)

    detector.check({"cpu_usage": 95, "memory_usage": 40}, service="svc-a", now=t0)
    alerts = detector.check(
        {"cpu_usage": 95, "memory_usage": 40}, service="svc-a", now=t0 + timedelta(seconds=300)
    )

    assert len(alerts) == 1
    assert alerts[0]["metric"] == "CPU"
    assert alerts[0]["service"] == "svc-a"


def test_breach_resets_when_value_drops_back_below_threshold():
    detector = make_detector()
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)

    detector.check({"cpu_usage": 95, "memory_usage": 40}, service="svc-a", now=t0)
    detector.check({"cpu_usage": 50, "memory_usage": 40}, service="svc-a", now=t0 + timedelta(seconds=120))
    alerts = detector.check(
        {"cpu_usage": 95, "memory_usage": 40}, service="svc-a", now=t0 + timedelta(seconds=300)
    )

    assert alerts == []  # le chrono a été réinitialisé par le retour sous le seuil


def test_no_alert_during_maintenance_window():
    rules = dict(RULES)
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    rules["maintenance_windows"] = [
        {
            "name": "campagne_promo",
            "start": (t0 - timedelta(hours=1)).isoformat(),
            "end": (t0 + timedelta(hours=1)).isoformat(),
            "services": ["svc-a"],
        }
    ]
    detector = AnomalyDetector(rules=rules)

    detector.check({"cpu_usage": 95, "memory_usage": 40}, service="svc-a", now=t0)
    alerts = detector.check(
        {"cpu_usage": 95, "memory_usage": 40}, service="svc-a", now=t0 + timedelta(seconds=300)
    )

    assert alerts == []  # fenêtre de maintenance active pour svc-a


def test_no_alert_when_consistent_with_trend_baseline():
    detector = make_detector()
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)

    # baseline habituelle déjà élevée (ex: charge hebdomadaire normale à 70%)
    baselines = {"cpu": 70}
    detector.check({"cpu_usage": 95, "memory_usage": 40}, service="svc-a", now=t0, baselines=baselines)
    alerts = detector.check(
        {"cpu_usage": 95, "memory_usage": 40},
        service="svc-a",
        now=t0 + timedelta(seconds=300),
        baselines=baselines,
    )

    # 95 < 70 * 1.5 (105) -> cohérent avec la tendance, pas d'alerte
    assert alerts == []


def test_alert_when_far_above_trend_baseline():
    detector = make_detector()
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)

    baselines = {"cpu": 30}
    detector.check({"cpu_usage": 95, "memory_usage": 40}, service="svc-a", now=t0, baselines=baselines)
    alerts = detector.check(
        {"cpu_usage": 95, "memory_usage": 40},
        service="svc-a",
        now=t0 + timedelta(seconds=300),
        baselines=baselines,
    )

    # 95 >= 30 * 1.5 (45) -> anomalie réelle
    assert len(alerts) == 1