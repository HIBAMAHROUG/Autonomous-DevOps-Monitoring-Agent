import requests


PROMETHEUS_URL = "http://localhost:9090/api/v1/query"


def query_prometheus(query):

    response = requests.get(
        PROMETHEUS_URL,
        params={"query": query}
    )

    return response.json()