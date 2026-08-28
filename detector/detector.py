from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone

import yaml

RULES_PATH = os.getenv("DETECTOR_RULES_PATH", "detector/rules.yaml")

MONITORED_METRICS = (
    ("cpu", "cpu_usage", "CPU"),
    ("memory", "memory_usage", "MEMORY"),
)


def _load_rules(path: str = RULES_PATH) -> dict:
    with open(path, "r", encoding="utf-8") as file:
        return yaml.safe_load(file) or {}


@dataclass
class AnomalyDetector:
    rules: dict = field(default_factory=_load_rules)
    _breach_since: dict[tuple[str, str], datetime] = field(default_factory=dict)
    _alerted: set[tuple[str, str]] = field(default_factory=set)

    def _in_maintenance_window(self, service: str, now: datetime):
        for window in self.rules.get("maintenance_windows") or []:
            if service not in window.get("services", []):
                continue
            start = datetime.fromisoformat(window["start"])
            end = datetime.fromisoformat(window["end"])
            if start <= now <= end:
                return True, window.get("name", "unnamed")
        return False, None

    def _passes_trend_check(
        self, metric_key: str, value: float, baseline: float | None
    ) -> bool:
        multiplier = self.rules.get(metric_key, {}).get("trend_multiplier")
        if multiplier is None or baseline is None or baseline <= 0:
            return True
        return value >= baseline * float(multiplier)

    def check(
        self,
        metrics: dict,
        service: str = "default",
        pod: str | None = None,
        baselines: dict | None = None,
        now: datetime | None = None,
    ) -> list[dict]:
        now = now or datetime.now(timezone.utc)
        baselines = baselines or {}
        alerts: list[dict] = []

        in_maintenance, window_name = self._in_maintenance_window(service, now)

        for rule_key, field_name, label in MONITORED_METRICS:
            rule = self.rules.get(rule_key)
            if not rule or field_name not in metrics:
                continue

            value = metrics.get(field_name)
            if value is None:
                continue
            value = float(value)

            threshold = float(rule["threshold"])
            duration = float(rule.get("duration", 0))
            state_key = (service, rule_key)

            if value <= threshold:
                self._breach_since.pop(state_key, None)
                self._alerted.discard(state_key)
                continue

            breach_start = self._breach_since.setdefault(state_key, now)
            sustained_for = (now - breach_start).total_seconds()

            if sustained_for < duration or in_maintenance:
                continue

            if not self._passes_trend_check(
                rule_key, value, baselines.get(rule_key)
            ):
                continue

            # Emit one event per breach. A new event is allowed only after
            # the metric returns below the threshold.
            if state_key in self._alerted:
                continue

            alert = {
                "timestamp": now.isoformat(),
                "service": service,
                "pod": pod,
                "metric": label,
                "metric_key": rule_key,
                "value": value,
                "threshold": threshold,
                "baseline": baselines.get(rule_key),
                "trend_multiplier": rule.get("trend_multiplier"),
                "sustained_seconds": round(sustained_for, 1),
                "required_duration": duration,
                "severity": "medium",
                "maintenance_window": window_name if in_maintenance else None,
            }
            alerts.append(alert)
            self._alerted.add(state_key)

        if alerts:
            os.makedirs("events", exist_ok=True)
            with open("events/alerts.json", "w", encoding="utf-8") as file:
                json.dump(alerts, file, indent=4, ensure_ascii=False)

        return alerts


_default_detector = AnomalyDetector()


def check_metrics(
    metrics: dict,
    service: str = "default",
    pod: str | None = None,
    baselines: dict | None = None,
) -> list[dict]:
    return _default_detector.check(
        metrics,
        service=service,
        pod=pod,
        baselines=baselines,
    )
