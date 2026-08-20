import os
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Optional, Any

from dotenv import load_dotenv
from influxdb_client import InfluxDBClient
from influxdb_client.client.write_api import SYNCHRONOUS

load_dotenv()


class MetricsStore:
    """Stockage des métriques avec support InfluxDB et fallback JSONL local."""

    ALLOWED_WINDOWS = {
        "1h": "1h",
        "6h": "6h",
        "12h": "12h",
        "24h": "24h",
        "1d": "1d",
        "7d": "7d",
        "30d": "30d",
    }

    def __init__(self, data_dir: str = "data"):
        self.influx_url = os.getenv("INFLUX_URL", "http://localhost:8086")
        self.token = os.getenv("INFLUX_TOKEN")
        self.org = os.getenv("INFLUX_ORG", "sre-org")
        self.bucket = os.getenv("INFLUX_BUCKET", "metrics")
        self.retention_days = 30
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        self.jsonl_file = self.data_dir / "metrics.jsonl"
        self._influx_client = None
        self.influx_enabled = False
        self._init_influx()

    def _init_influx(self):
        """Initialise la connexion à InfluxDB."""
        try:
            if not self.token:
                print("⚠️  INFLUX_TOKEN manquant dans .env")
                return

            self._influx_client = InfluxDBClient(
                url=self.influx_url,
                token=self.token,
                org=self.org
            )

            if self._influx_client.ping():
                buckets = self._influx_client.buckets_api().find_buckets().buckets
                bucket_names = [b.name for b in buckets]
                if self.bucket in bucket_names:
                    self.influx_enabled = True
                    print(f"✅ Connexion InfluxDB établie (bucket: {self.bucket})")
                else:
                    print(f"⚠️  Bucket '{self.bucket}' introuvable dans InfluxDB")
            else:
                print("⚠️  InfluxDB inaccessible (ping échoué)")
        except Exception as e:
            print(f"⚠️  Erreur de connexion InfluxDB: {e}")
            self.influx_enabled = False

    def _get_influx_client(self) -> Optional[InfluxDBClient]:
        """Retourne le client InfluxDB si disponible."""
        if self.influx_enabled and self._influx_client:
            return self._influx_client
        return None

    def _write_to_jsonl(self, data: Dict[str, Any]):
        """Écrit une métrique dans le fichier JSONL de fallback."""
        try:
            with open(self.jsonl_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(data) + "\n")
        except Exception as e:
            print(f"⚠️  Erreur d'écriture JSONL: {e}")

    def _read_jsonl(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Lit les métriques depuis le fichier JSONL de fallback."""
        records = []
        try:
            if not self.jsonl_file.exists():
                return records

            with open(self.jsonl_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            records.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue

            records.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

            if limit and limit > 0:
                return records[:limit]
            return records
        except Exception as e:
            print(f"⚠️  Erreur de lecture JSONL: {e}")
            return []

    def write_metric(
        self,
        metric: dict[str, Any]
    ) -> None:
        """Write one metric to InfluxDB, with JSONL fallback."""

        if not metric:
            return

        # Make a safe copy so we never modify the caller's dictionary.
        data = dict(metric)

        timestamp = data.pop("timestamp", None)

        if timestamp is None:
            timestamp = datetime.now(timezone.utc)
        elif isinstance(timestamp, str):
            try:
                timestamp = datetime.fromisoformat(
                    timestamp.replace("Z", "+00:00")
                )
            except ValueError:
                timestamp = datetime.now(timezone.utc)

        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)

        # Try InfluxDB first.
        if self.influx_enabled and self._influx_client is not None:
            try:
                from influxdb_client import Point, WritePrecision

                point = Point("system_metrics")

                for key, value in data.items():

                    if value is None:
                        continue

                    if isinstance(value, bool):
                        point = point.field(key, value)

                    elif isinstance(value, (int, float)):
                        point = point.field(key, float(value))

                    elif isinstance(value, str):
                        point = point.field(key, value)

                point = point.time(
                    timestamp,
                    WritePrecision.S
                )

                write_api = self._influx_client.write_api(write_options=SYNCHRONOUS)

                try:
                    write_api.write(
                        bucket=self.bucket,
                        org=self.org,
                        record=point
                    )
                finally:
                    write_api.close()

                print("✅ Metric écrite dans InfluxDB", flush=True)
                return

            except Exception as e:
                print(
                    f"❌ Erreur écriture InfluxDB: {type(e).__name__}: {e}",
                    flush=True
                )

        # JSONL fallback.
        local_metric = dict(data)
        local_metric["timestamp"] = timestamp.isoformat()

        self._write_local(local_metric)
    def get_history(
        self,
        window: str = "24h",
        limit: int = 100
    ) -> list[dict[str, Any]]:

        limit = max(1, min(int(limit), 5000))

        if self.influx_enabled and self._influx_client is not None:

            flux_window = self.ALLOWED_WINDOWS.get(
                str(window).strip(),
                "24h"
            )

            flux = f'''
from(bucket: "{self.bucket}")
    |> range(start: -{flux_window})
    |> filter(fn: (r) => r["_measurement"] == "system_metrics")
    |> pivot(
        rowKey: ["_time"],
        columnKey: ["_field"],
        valueColumn: "_value"
    )
    |> sort(columns: ["_time"], desc: true)
    |> limit(n: {limit})
'''

            try:
                query_api = self._influx_client.query_api()

                tables = query_api.query(
                    query=flux,
                    org=self.org
                )

                results = []

                ignored_keys = {
                    "_start",
                    "_stop",
                    "_measurement",
                    "_field",
                    "_value",
                    "result",
                    "table",
                    "start",
                    "stop"
                }

                for table in tables:
                    for record in table.records:

                        values = record.values

                        raw = {}

                        for key, value in values.items():

                            if key in ignored_keys:
                                continue

                            if key.startswith("_"):
                                continue

                            raw[key] = value

                        timestamp = values.get("_time")

                        if timestamp is None:
                            timestamp = datetime.now(timezone.utc)

                        if hasattr(timestamp, "isoformat"):
                            timestamp = timestamp.isoformat()

                        results.append(
                            {
                                "timestamp": timestamp,
                                "raw": raw
                            }
                        )

                return results

            except Exception as e:
                print(
                    f"⚠️ Erreur lecture InfluxDB: {e}"
                )

        return self._read_jsonl(limit=limit)
    def get_latest(self) -> Optional[Dict[str, Any]]:
        """
        Retourne la dernière métrique disponible.
        """
        history = self.get_history(window="30d", limit=1)
        if history:
            return history[0]
        return None

    def health_check(self) -> Dict[str, Any]:
        """
        Vérifie l'état du stockage.
        """
        status = {
            "status": "ok",
            "storage": "jsonl" if not self.influx_enabled else "influxdb",
            "bucket": self.bucket,
            "org": self.org,
            "retention_days": self.retention_days,
        }

        if self.influx_enabled:
            try:
                client = self._get_influx_client()
                if client and client.ping():
                    status["influx_status"] = "connected"
                else:
                    status["influx_status"] = "disconnected"
                    status["status"] = "degraded"
            except:
                status["influx_status"] = "error"
                status["status"] = "degraded"

        return status





