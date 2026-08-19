from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any

from .influx import _get_client


class MetricsStore:
    def __init__(self):
        self.measurement = "monitoring_agent_metrics"
        self.bucket = os.getenv("INFLUX_BUCKET", "metrics")
        self.org = os.getenv("INFLUX_ORG", "sre-org")
        self.retention_days = int(os.getenv("METRICS_RETENTION_DAYS", "30"))

        # InfluxDB est considéré comme configuré si une URL est disponible.
        self.influx_enabled = bool(
            os.getenv("INFLUX_URL", "http://localhost:8086")
        )

    def write_metrics(
        self,
        raw_metrics: dict[str, float],
        normalized_metrics: dict[str, float],
        aggregate: dict[str, Any],
    ) -> None:
        client = _get_client()

        point = {
            "measurement": self.measurement,
            "fields": {
                "raw_metrics": json.dumps(raw_metrics),
                "normalized_metrics": json.dumps(normalized_metrics),
                "aggregate": json.dumps(aggregate),
            },
            "time": datetime.now(timezone.utc),
        }

        write_api = client.write_api()

        try:
            write_api.write(
                bucket=self.bucket,
                org=self.org,
                record=point,
            )
        finally:
            write_api.close()

    def get_history(
        self,
        window: str = "24h",
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Retourne l'historique des métriques depuis InfluxDB.

        Exemples de window :
        - 1h
        - 6h
        - 24h
        - 7d
        - 30d
        """

        window = window.strip().lower()

        if window.endswith("h"):
            hours = float(window[:-1])
            start = f"-{hours}h"
        elif window.endswith("d"):
            days = float(window[:-1])
            start = f"-{days}d"
        elif window.endswith("m"):
            minutes = float(window[:-1])
            start = f"-{minutes}m"
        else:
            start = "-24h"

        limit = max(1, min(int(limit), 10000))

        client = _get_client()
        query_api = client.query_api()

        flux = f'''
        from(bucket: "{self.bucket}")
          |> range(start: {start})
          |> filter(fn: (r) => r._measurement == "{self.measurement}")
          |> pivot(
              rowKey: ["_time"],
              columnKey: ["_field"],
              valueColumn: "_value"
          )
          |> sort(columns: ["_time"], desc: true)
          |> limit(n: {limit})
        '''

        tables = query_api.query(
            flux,
            org=self.org,
        )

        results: list[dict[str, Any]] = []

        for table in tables:
            for record in table.records:
                results.append(
                    {
                        "time": record.get_time().isoformat()
                        if record.get_time()
                        else None,
                        "raw": json.loads(
                            record.values.get("raw_metrics", "{}")
                        ),
                        "normalized": json.loads(
                            record.values.get("normalized_metrics", "{}")
                        ),
                        "aggregate": json.loads(
                            record.values.get("aggregate", "{}")
                        ),
                    }
                )

        return results

    def get_latest(self) -> dict[str, Any] | None:
        """
        Retourne la dernière métrique disponible.
        """

        history = self.get_history(window="30d", limit=1)

        if not history:
            return None

        return history[0]

    def list_metrics(self, limit: int = 60) -> list[dict[str, Any]]:
        """
        Compatibilité avec l'ancienne API.
        """
        return self.get_history(window="30d", limit=limit)
