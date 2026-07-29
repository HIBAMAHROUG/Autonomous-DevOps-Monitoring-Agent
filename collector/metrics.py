import os
import requests


PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://localhost:9090/api/v1/query")
PROMETHEUS_TOKEN = os.getenv("PROMETHEUS_TOKEN")  # None si pas défini


def _get_headers():
    if PROMETHEUS_TOKEN:
        return {"Authorization": f"Bearer {PROMETHEUS_TOKEN}"}
    return {}


def query_prometheus(query):

    response = requests.get(
        PROMETHEUS_URL,
        params={"query": query},
        headers=_get_headers(),
        timeout=10
    )

    response.raise_for_status()

    data = response.json()

    result = data["data"]["result"]

    if not result:
        raise ValueError(f"No data returned for query: {query}")

    return float(result[0]["value"][1])


def get_cpu():

    query = '100 - (avg(rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)'

    return query_prometheus(query)


def get_memory():

    query = """
    (1 - (node_memory_MemAvailable_bytes /
    node_memory_MemTotal_bytes)) * 100
    """

    return query_prometheus(query)


def get_network():

    query = """
    sum(rate(node_network_receive_bytes_total{device!="lo"}[5m]))
    """

    return query_prometheus(query)


def get_disk():

    query = """
    ((node_filesystem_size_bytes{fstype!="tmpfs"} -
    node_filesystem_avail_bytes{fstype!="tmpfs"}) /
    node_filesystem_size_bytes{fstype!="tmpfs"}) * 100
    """

    return query_prometheus(query)