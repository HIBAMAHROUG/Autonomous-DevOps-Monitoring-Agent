from __future__ import annotations

import os
import re
import time

import requests

LOKI_URL = os.getenv("LOKI_URL", "http://loki:3100").rstrip("/")
MAX_LINES = int(os.getenv("LOKI_MAX_LINES", "500"))
MAX_DURATION = float(os.getenv("LOKI_MAX_DURATION", "5"))
LOKI_LOOKBACK = os.getenv("LOKI_LOOKBACK", "10m")

LEVEL_PATTERN = re.compile(
    r"\b(WARN|WARNING|ERROR|FATAL|OOMKilled|CrashLoopBackOff)\b",
    re.IGNORECASE,
)


class LogCollectionError(Exception):
    pass


def _query(url: str, query: str) -> dict:
    params = {
        "query": query,
        "limit": MAX_LINES,
        "direction": "backward",
        "since": LOKI_LOOKBACK,
    }
    response = requests.get(url, params=params, timeout=(2, MAX_DURATION))
    response.raise_for_status()
    return response.json()


def get_pod_logs(pod: str | None, namespace: str = "default"):
    start = time.perf_counter()
    if not pod:
        return {
            "pod": pod,
            "namespace": namespace,
            "logs": [],
            "count": 0,
            "duration_seconds": 0,
        }

    url = f"{LOKI_URL}/loki/api/v1/query_range"

    try:
        data = _query(url, f'{{namespace="{namespace}",pod="{pod}"}}')

        logs = []
        for stream in data.get("data", {}).get("result", []):
            for timestamp, message in stream.get("values", []):
                logs.append({"timestamp": timestamp, "message": message})

        logs = logs[:MAX_LINES]

        # Keep diagnostic error logs, but do not fail the incident if Loki
        # contains only INFO logs. The orchestrator has a metric fallback.
        filtered = [
            log for log in logs if LEVEL_PATTERN.search(log["message"])
        ]

        elapsed = time.perf_counter() - start
        if elapsed > MAX_DURATION:
            raise LogCollectionError(
                f"Loki retrieval exceeded {MAX_DURATION}s"
            )

        return {
            "pod": pod,
            "namespace": namespace,
            "logs": filtered,
            "raw_count": len(logs),
            "count": len(filtered),
            "duration_seconds": round(elapsed, 3),
        }

    except requests.RequestException as exc:
        raise LogCollectionError(
            f"Unable to retrieve logs from Loki at {url}: {exc}"
        ) from exc
