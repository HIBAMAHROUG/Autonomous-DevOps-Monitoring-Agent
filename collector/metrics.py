from collector.prometheus_client import query_prometheus


def get_cpu():

    query = '100 - (avg by(instance)(irate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)'

    return query_prometheus(query)



def get_memory():

    query = "node_memory_MemAvailable_bytes"

    return query_prometheus(query)



def get_network():

    query = "node_network_receive_bytes_total"

    return query