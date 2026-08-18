from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

from .influx import _get_client


class MetricsStore:
    def __init__(self):
        self.measurement = "monitoring_agent_metrics"
        self.bucket = os.getenv("INFLUX_BUCKET", "metrics")
        self.org = os.getenv("INFLUX_ORG", "sre-org")

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

    def list_metrics(self, limit: int = 60) -> list[dict[str, Any]]:
        client = _get_client()
        query_api = client.query_api()

        flux = f'''
        from(bucket: "{self.bucket}")
          |> range(start: -30d)
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
                        "time": record.get_time(),
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
