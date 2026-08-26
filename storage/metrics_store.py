from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from influxdb_client import InfluxDBClient

load_dotenv()


class MetricsStore:
    def __init__(self):
        self.influx_url = os.getenv(
            "INFLUX_URL",
            "http://localhost:8086",
        )

        self.influx_token = os.getenv(
            "INFLUX_TOKEN",
            "",
        )

        self.org = os.getenv(
            "INFLUX_ORG",
            "sre-org",
        )

        self.bucket = os.getenv(
            "INFLUX_BUCKET",
            "metrics",
        )

        self.retention_days = int(
            os.getenv(
                "METRICS_RETENTION_DAYS",
                "30",
            )
        )

        self.influx_enabled = bool(
            self.influx_url
            and self.influx_token
            and self.org
            and self.bucket
        )

        self.client = None
        self.query_api = None

        if self.influx_enabled:
            self.client = InfluxDBClient(
                url=self.influx_url,
                token=self.influx_token,
                org=self.org,
            )
            self.query_api = self.client.query_api()

        self.local_file = Path(
            os.getenv(
                "METRICS_LOCAL_FILE",
                "storage/metrics.jsonl",
            )
        )

    def _ensure_local_directory(self):
        self.local_file.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

    def _write_local(self, metric: dict[str, Any]):
        self._ensure_local_directory()

        with self.local_file.open(
            "a",
            encoding="utf-8",
        ) as file:
            file.write(
                json.dumps(
                    metric,
                    default=str,
                )
                + "\n"
            )

    def write_metric(
        self,
        metric: dict[str, Any],
    ) -> None:
        """
        Enregistre une métrique dans InfluxDB.
        En cas d'échec, utilise le fichier JSONL local.
        """

        if not metric:
            return

        if self.influx_enabled and self.client is not None:
            try:
                from influxdb_client import Point

                timestamp = metric.get("timestamp")

                if timestamp is None:
                    timestamp = datetime.now(timezone.utc)

                point = Point("system_metrics")

                for key, value in metric.items():
                    if key == "timestamp":
                        continue

                    if isinstance(value, bool):
                        point = point.field(
                            key,
                            value,
                        )

                    elif isinstance(
                        value,
                        (int, float),
                    ):
                        point = point.field(
                            key,
                            float(value),
                        )

                point = point.time(timestamp)

                write_api = self.client.write_api()

                write_api.write(
                    bucket=self.bucket,
                    org=self.org,
                    record=point,
                )

                write_api.close()

                return

            except Exception:
                # Fallback local si InfluxDB rencontre un problème.
                pass

        self._write_local(metric)

    def get_history(
        self,
        window: str = "24h",
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Retourne l'historique des métriques depuis InfluxDB.
        """

        limit = max(1, min(int(limit), 5000))

        if self.influx_enabled and self.query_api is not None:
            flux = f'''
from(bucket: "{self.bucket}")
    |> range(start: -{window})
    |> filter(fn: (r) => r["_measurement"] == "system_metrics")
    |> pivot(
        rowKey: ["_time"],
        columnKey: ["_field"],
        valueColumn: "_value"
    )
    |> sort(columns: ["_time"], desc: true)
    |> limit(n: {limit})
'''

            tables = self.query_api.query(
                flux,
                org=self.org,
            )

            results = []

            for table in tables:
                for record in table.records:
                    values = record.values

                    raw = {}

                    for key, value in values.items():
                        if key.startswith("_"):
                            continue

                        if key in {
                            "result",
                            "table",
                            "start",
                            "stop",
                        }:
                            continue

                        raw[key] = value

                    timestamp = record.get_time()

                    results.append(
                        {
                            "timestamp": (
                                timestamp.isoformat()
                                if timestamp
                                else None
                            ),
                            "raw": raw,
                        }
                    )

            return results[:limit]

        return self._read_local(limit)

    def _read_local(
        self,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Lit les métriques depuis le fallback JSONL.
        """

        if not self.local_file.exists():
            return []

        results = []

        with self.local_file.open(
            "r",
            encoding="utf-8",
        ) as file:

            for line in file:
                line = line.strip()

                if not line:
                    continue

                try:
                    results.append(
                        json.loads(line)
                    )
                except json.JSONDecodeError:
                    continue

        results.reverse()

        return results[:limit]

    def get_latest(
        self,
    ) -> dict[str, Any] | None:
        """
        Retourne la dernière métrique disponible.
        """

        history = self.get_history(
            window="30d",
            limit=1,
        )

        if not history:
            return None

        return history[0]

    def health_check(self) -> dict[str, Any]:
        """
        Vérifie l'état du stockage InfluxDB.
        """

        if not self.influx_enabled or self.client is None:
            return {
                "status": "ok",
                "storage": "local",
            }

        try:
            health = self.client.health()

            if health.status == "pass":
                return {
                    "status": "ok",
                    "storage": "influxdb",
                }

            return {
                "status": "degraded",
                "storage": "influxdb",
            }

        except Exception as e:
            return {
                "status": "degraded",
                "storage": "influxdb",
                "error": str(e),
            }

    def close(self):
        """
        Ferme proprement la connexion InfluxDB.
        """

        if self.client is not None:
            self.client.close()

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass
