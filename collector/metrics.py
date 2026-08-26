from __future__ import annotations

import os

import requests
from dotenv import load_dotenv


# ============================================================
# ENVIRONMENT
# ============================================================

load_dotenv()


PROMETHEUS_URL = os.getenv(
    "PROMETHEUS_URL",
    "http://localhost:9090/api/v1/query",
)

PROMETHEUS_TOKEN = os.getenv(
    "PROMETHEUS_TOKEN"
)

PROMETHEUS_REQUIRE_AUTH = os.getenv(
    "PROMETHEUS_REQUIRE_AUTH",
    "true",
).lower() in {
    "1",
    "true",
    "yes",
    "on",
}

PROMETHEUS_TIMEOUT = float(
    os.getenv(
        "PROMETHEUS_TIMEOUT",
        "7",
    )
)


# ============================================================
# HEADERS
# ============================================================

def _get_headers() -> dict[str, str]:

    if PROMETHEUS_REQUIRE_AUTH:

        if not PROMETHEUS_TOKEN:
            raise RuntimeError(
                "PROMETHEUS_TOKEN is required "
                "when PROMETHEUS_REQUIRE_AUTH=true"
            )

        return {
            "Authorization": (
                f"Bearer {PROMETHEUS_TOKEN}"
            )
        }

    return {}


# ============================================================
# PROMETHEUS QUERY
# ============================================================

def query_prometheus(
    query: str,
) -> float:

    response = requests.get(
        PROMETHEUS_URL,
        params={
            "query": query,
        },
        headers=_get_headers(),
        timeout=PROMETHEUS_TIMEOUT,
    )

    response.raise_for_status()

    data = response.json()

    if data.get("status") != "success":
        raise RuntimeError(
            f"Prometheus query failed: {data}"
        )

    result = (
        data
        .get("data", {})
        .get("result", [])
    )

    if not result:
        raise ValueError(
            f"No data returned for query:\n{query}"
        )

    return float(
        result[0]["value"][1]
    )


# ============================================================
# CPU
# ============================================================

def get_cpu() -> float:

    query = """
    100 - (
        avg(
            rate(
                node_cpu_seconds_total{
                    mode="idle"
                }[5m]
            )
        ) * 100
    )
    """

    return query_prometheus(query)


# ============================================================
# MEMORY
# ============================================================

def get_memory() -> float:

    query = """
    (
        1 -
        (
            node_memory_MemAvailable_bytes
            /
            node_memory_MemTotal_bytes
        )
    ) * 100
    """

    return query_prometheus(query)


# ============================================================
# NETWORK
# ============================================================

def get_network() -> float:

    query = """
    sum(
        rate(
            node_network_receive_bytes_total{
                device!="lo"
            }[5m]
        )
    )
    """

    return query_prometheus(query)


# ============================================================
# DISK
# ============================================================

def get_disk() -> float | None:

    query = """
    (
        1 -
        (
            sum(
                node_filesystem_avail_bytes{
                    fstype!="tmpfs",
                    mountpoint!=""
                }
            )
            /
            sum(
                node_filesystem_size_bytes{
                    fstype!="tmpfs",
                    mountpoint!=""
                }
            )
        )
    ) * 100
    """

    try:

        return query_prometheus(query)

    except ValueError as e:

        print(
            f"WARNING: Disk metric unavailable: {e}",
            flush=True,
        )

        return None


# ============================================================
# HIGHEST CPU POD
# ============================================================

def get_highest_cpu_pod() -> str | None:

    query = """
    topk(
        1,
        sum by (namespace, pod) (
            rate(
                container_cpu_usage_seconds_total{
                    pod!="",
                    container!="",
                    container!="POD"
                }[5m]
            )
        )
    )
    """

    response = requests.get(
        PROMETHEUS_URL,
        params={
            "query": query,
        },
        headers=_get_headers(),
        timeout=PROMETHEUS_TIMEOUT,
    )

    response.raise_for_status()

    data = response.json()

    result = (
        data
        .get("data", {})
        .get("result", [])
    )

    if not result:
        return None

    metric = result[0].get(
        "metric",
        {}
    )

    namespace = metric.get(
        "namespace",
        "default",
    )

    pod = metric.get(
        "pod"
    )

    if not pod:
        return None

    return f"{namespace}/{pod}"