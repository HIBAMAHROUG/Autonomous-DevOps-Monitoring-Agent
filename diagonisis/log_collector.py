import os
import time
import requests


LOKI_URL = os.getenv("LOKI_URL", "http://localhost:3100")
MAX_LINES = 500
MAX_DURATION = 5


class LogCollectionError(Exception):
    pass


def get_pod_logs(pod, namespace="default"):
    start_time = time.perf_counter()

    url = f"{LOKI_URL}/loki/api/v1/query_range"

    params = {
        "query": f'{{namespace="{namespace}",pod="{pod}"}}',
        "limit": MAX_LINES,
        "direction": "backward",
    }

    try:
        response = requests.get(
            url,
            params=params,
            timeout=MAX_DURATION,
        )

        response.raise_for_status()

        data = response.json()

        logs = []

        for stream in data.get("data", {}).get("result", []):
            for entry in stream.get("values", []):
                timestamp, message = entry

                logs.append({
                    "timestamp": timestamp,
                    "message": message
                })

        logs = logs[:MAX_LINES]

        filtered_logs = [
            log for log in logs
            if any(
                level in log["message"].upper()
                for level in ["WARN", "ERROR", "FATAL"]
            )
        ]

        elapsed = time.perf_counter() - start_time

        if elapsed > MAX_DURATION:
            raise LogCollectionError(
                f"Log retrieval exceeded {MAX_DURATION} seconds"
            )

        return {
            "pod": pod,
            "namespace": namespace,
            "logs": filtered_logs,
            "count": len(filtered_logs),
            "duration_seconds": round(elapsed, 3)
        }

    except requests.RequestException as exc:
        raise LogCollectionError(
            f"Unable to retrieve logs from Loki: {exc}"
        ) from exc