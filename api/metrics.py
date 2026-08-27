import os
import requests

from fastapi import APIRouter, HTTPException


router = APIRouter(prefix="/api", tags=["metrics"])

PROMETHEUS_URL = os.getenv(
    "PROMETHEUS_URL",
    "http://prometheus:9090",
)


def query_prometheus(query: str):
    try:
        response = requests.get(
            f"{PROMETHEUS_URL}/api/v1/query",
            params={"query": query},
            timeout=5,
        )

        response.raise_for_status()

        data = response.json()

        if data.get("status") != "success":
            raise RuntimeError(data)

        return data["data"]["result"]

    except requests.RequestException as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Prometheus unavailable: {exc}",
        )


@router.get("/metrics")
def get_metrics():
    cpu = query_prometheus(
        '100 - avg(rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100'
    )

    memory = query_prometheus(
        '100 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes * 100)'
    )

    network_rx = query_prometheus(
        "sum(rate(node_network_receive_bytes_total[5m]))"
    )

    network_tx = query_prometheus(
        "sum(rate(node_network_transmit_bytes_total[5m]))"
    )

    return {
        "source": "prometheus",
        "metrics": {
            "cpu": cpu,
            "memory": memory,
            "network_receive": network_rx,
            "network_transmit": network_tx,
        },
    }