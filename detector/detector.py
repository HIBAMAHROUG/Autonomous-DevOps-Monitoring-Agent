from __future__ import annotations

import json
import os

from dataclasses import dataclass, field
from datetime import datetime, timezone

import yaml


# ============================================================
# CONFIGURATION
# ============================================================

RULES_PATH = os.getenv(
    "DETECTOR_RULES_PATH",
    "detector/rules.yaml",
)


# ============================================================
# MONITORED METRICS
# ============================================================

MONITORED_METRICS = (
    (
        "cpu",
        "cpu_usage",
        "CPU",
    ),
    (
        "memory",
        "memory_usage",
        "MEMORY",
    ),
)


# ============================================================
# RULE LOADER
# ============================================================

def _load_rules(
    path: str = RULES_PATH,
) -> dict:

    with open(
        path,
        "r",
        encoding="utf-8",
    ) as file:

        return (
            yaml.safe_load(file)
            or {}
        )


# ============================================================
# ANOMALY DETECTOR
# ============================================================

@dataclass
class AnomalyDetector:

    rules: dict = field(
        default_factory=_load_rules
    )

    # Suivi du début du dépassement
    # pour chaque service / métrique.
    _breach_since: dict[
        tuple[str, str],
        datetime,
    ] = field(
        default_factory=dict
    )

    # ========================================================
    # MAINTENANCE WINDOW
    # ========================================================

    def _in_maintenance_window(
        self,
        service: str,
        now: datetime,
    ) -> tuple[
        bool,
        str | None,
    ]:

        for window in (
            self.rules.get(
                "maintenance_windows"
            )
            or []
        ):

            if service not in (
                window.get(
                    "services",
                    [],
                )
            ):

                continue

            start = datetime.fromisoformat(
                window["start"]
            )

            end = datetime.fromisoformat(
                window["end"]
            )

            if start <= now <= end:

                return (
                    True,
                    window.get(
                        "name",
                        "unnamed",
                    ),
                )

        return (
            False,
            None,
        )

    # ========================================================
    # TREND / BASELINE CHECK
    # ========================================================

    def _passes_trend_check(
        self,
        metric_key: str,
        value: float,
        baseline: float | None,
    ) -> bool:

        multiplier = (
            self.rules
            .get(
                metric_key,
                {},
            )
            .get(
                "trend_multiplier"
            )
        )

        # Si aucune baseline n'est disponible,
        # on ne bloque pas l'alerte.
        if (
            multiplier is None
            or baseline is None
            or baseline <= 0
        ):

            return True

        return (
            value
            >=
            baseline * multiplier
        )

    # ========================================================
    # CHECK
    # ========================================================

    def check(
        self,
        metrics: dict,
        service: str = "default",
        pod: str | None = None,
        baselines: dict | None = None,
        now: datetime | None = None,
    ) -> list[dict]:

        now = (
            now
            or datetime.now(
                timezone.utc
            )
        )

        baselines = (
            baselines
            or {}
        )

        alerts: list[dict] = []

        # ====================================================
        # MAINTENANCE
        # ====================================================

        in_maintenance, window_name = (
            self._in_maintenance_window(
                service,
                now,
            )
        )

        # ====================================================
        # RULES
        # ====================================================

        for (
            rule_key,
            field_name,
            label,
        ) in MONITORED_METRICS:

            rule = self.rules.get(
                rule_key
            )

            if not rule:

                continue

            if field_name not in metrics:

                continue

            value = metrics.get(
                field_name
            )

            # Une valeur None ne doit jamais
            # provoquer une comparaison numérique.
            if value is None:

                continue

            value = float(value)

            threshold = float(
                rule["threshold"]
            )

            duration = float(
                rule.get(
                    "duration",
                    0,
                )
            )

            state_key = (
                service,
                rule_key,
            )

            # =================================================
            # UNDER THRESHOLD
            # =================================================

            if value <= threshold:

                self._breach_since.pop(
                    state_key,
                    None,
                )

                continue

            # =================================================
            # START / CONTINUE BREACH
            # =================================================

            breach_start = (
                self._breach_since.setdefault(
                    state_key,
                    now,
                )
            )

            sustained_for = (
                now - breach_start
            ).total_seconds()

            # =================================================
            # DURATION
            # =================================================

            if sustained_for < duration:

                continue

            # =================================================
            # MAINTENANCE WINDOW
            # =================================================

            if in_maintenance:

                continue

            # =================================================
            # BASELINE / TREND
            # =================================================

            baseline = baselines.get(
                rule_key
            )

            if not self._passes_trend_check(
                rule_key,
                value,
                baseline,
            ):

                continue

            # =================================================
            # ALERT
            # =================================================

            alert = {
                "timestamp": now.isoformat(),
                "service": service,
                "pod": pod,
                "metric": label,
                "metric_key": rule_key,
                "value": value,
                "threshold": threshold,
                "baseline": baseline,
                "trend_multiplier": rule.get(
                    "trend_multiplier"
                ),
                "sustained_seconds": round(
                    sustained_for,
                    1,
                ),
                "required_duration": duration,
                "severity": "CRITICAL",
                "maintenance_window": (
                    window_name
                    if in_maintenance
                    else None
                ),
            }

            alerts.append(
                alert
            )

        # ====================================================
        # JSON EVENT
        # ====================================================

        if alerts:

            os.makedirs(
                "events",
                exist_ok=True,
            )

            with open(
                "events/alerts.json",
                "w",
                encoding="utf-8",
            ) as file:

                json.dump(
                    alerts,
                    file,
                    indent=4,
                    ensure_ascii=False,
                )

        return alerts


# ============================================================
# DEFAULT DETECTOR
# ============================================================

_default_detector = (
    AnomalyDetector()
)


# ============================================================
# COMPATIBILITY WRAPPER
# ============================================================

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