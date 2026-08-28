# ============================================================
# PROMETHEUS
# ============================================================
import os
import requests
PROMETHEUS_URL = os.getenv(
    "PROMETHEUS_URL",
    "http://prometheus:9090",
)


INFRA_QUERIES = {

    "cpu_percent": (
        '100 - (avg(rate('
        'node_cpu_seconds_total{mode="idle"}[5m]'
        ')) * 100)'
    ),

    "memory_percent": (
        '(1 - (node_memory_MemAvailable_bytes / '
        'node_memory_MemTotal_bytes)) * 100'
    ),

    "network_receive": (
        'sum(rate('
        'node_network_receive_bytes_total{device!="lo"}[5m]'
        '))'
    ),

    "network_transmit": (
        'sum(rate('
        'node_network_transmit_bytes_total{device!="lo"}[5m]'
        '))'
    ),

    "node_exporter_up": (
        'up{job="node-exporter"}'
    ),

    "prometheus_up": (
        'up{job="prometheus"}'
    ),
}


def _query_prometheus(expr: str) -> float | None:

    try:

        response = requests.get(
            f"{PROMETHEUS_URL}/api/v1/query",
            params={"query": expr},
            timeout=5,
        )

        response.raise_for_status()

        payload = response.json()

        if payload.get("status") != "success":
            return None

        result = (
            payload
            .get("data", {})
            .get("result", [])
        )

        if not result:
            return None

        return float(
            result[0]["value"][1]
        )

    except (
        requests.RequestException,
        ValueError,
        KeyError,
        TypeError,
        IndexError,
    ):
        return None


# ============================================================
# INFRASTRUCTURE
# ============================================================

@dashboard_api.route(
    "/api/dashboard/infra",
    methods=["GET"],
)
def infra():

    if not _check_api_key():
        return jsonify({
            "error": "Unauthorized"
        }), 401

    metrics = {
        key: _query_prometheus(expression)
        for key, expression in INFRA_QUERIES.items()
    }

    return jsonify({

        "source": "prometheus",

        "prometheus_url": PROMETHEUS_URL,

        "metrics": metrics,

        "cpu_percent": metrics.get(
            "cpu_percent"
        ),

        "memory_percent": metrics.get(
            "memory_percent"
        ),

        "network_receive_bytes_per_second":
            metrics.get(
                "network_receive"
            ),

        "network_transmit_bytes_per_second":
            metrics.get(
                "network_transmit"
            ),

        "node_exporter_up":
            metrics.get(
                "node_exporter_up"
            ),

        "prometheus_up":
            metrics.get(
                "prometheus_up"
            ),
    })