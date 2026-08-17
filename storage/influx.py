"""
Connecteur InfluxDB — utilisé par le pipeline de collecte de métriques
(story SRE : collecte toutes les 30s, historique 30 jours minimum).

Ce module ne fait PAS partie du module remediation, mais remediation/
peut s'en servir en lecture pour enrichir une décision avec la valeur
brute de la métrique au moment de l'anomalie (context enrichment),
via `query_recent_points`.

pip install influxdb-client
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any

from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

_CLIENT: InfluxDBClient | None = None


def _get_client() -> InfluxDBClient:
    global _CLIENT
    if _CLIENT is None:
        _CLIENT = InfluxDBClient(
            url=os.getenv("INFLUX_URL", "http://localhost:8086"),
            token=os.getenv("INFLUX_TOKEN", ""),
            org=os.getenv("INFLUX_ORG", "sre-org"),
        )
    return _CLIENT


def write_metric(
    measurement: str,
    fields: dict[str, float],
    tags: dict[str, str] | None = None,
    timestamp: datetime | None = None,
) -> None:
    """
    Écrit un point de métrique. Exemple :
        write_metric(
            "system_metrics",
            fields={"cpu_utilization": 87.5, "memory_utilization": 91.2},
            tags={"component": "worker-node", "instance_id": "i-0123"},
        )
    """
    bucket = os.getenv("INFLUX_BUCKET", "metrics")
    point = Point(measurement)
    for k, v in (tags or {}).items():
        point = point.tag(k, v)
    for k, v in fields.items():
        point = point.field(k, v)
    if timestamp:
        point = point.time(timestamp, WritePrecision.S)

    client = _get_client()
    write_api = client.write_api(write_options=SYNCHRONOUS)
    write_api.write(bucket=bucket, record=point)


def query_recent_points(
    measurement: str,
    component: str,
    minutes: int = 10,
) -> list[dict[str, Any]]:
    """
    Récupère les derniers points pour un composant donné. Utile pour
    donner du contexte à une décision de remédiation (ex: afficher
    l'évolution de la métrique dans les minutes précédant l'anomalie).
    """
    bucket = os.getenv("INFLUX_BUCKET", "metrics")
    org = os.getenv("INFLUX_ORG", "sre-org")

    flux = f'''
    from(bucket: "{bucket}")
      |> range(start: -{minutes}m)
      |> filter(fn: (r) => r._measurement == "{measurement}")
      |> filter(fn: (r) => r.component == "{component}")
    '''

    client = _get_client()
    query_api = client.query_api()
    tables = query_api.query(flux, org=org)

    points: list[dict[str, Any]] = []
    for table in tables:
        for record in table.records:
            points.append(
                {
                    "time": record.get_time(),
                    "field": record.get_field(),
                    "value": record.get_value(),
                }
            )
    return points


def close_client() -> None:
    global _CLIENT
    if _CLIENT is not None:
        _CLIENT.close()
        _CLIENT = None