import time
from detector.detector import check_metrics
from logger import logger
from collector.metrics import (
    get_cpu,
    get_memory,
    get_network,
    get_disk
)
from collector.processing import aggregate_metrics, normalize_metrics
from storage import MetricsStore


STORE = MetricsStore()


def collect_metrics():

    logger.info("Collecting metrics...")

    cpu = get_cpu()
    memory = get_memory()
    network = get_network()
    disk = get_disk()

    metrics = {
        "cpu_usage": cpu,
        "memory_usage": memory,
        "network_usage": network,
        "disk_usage": disk
    }

    normalized_metrics = normalize_metrics(metrics)
    recent_metrics = STORE.list_metrics(limit=60)
    aggregate = aggregate_metrics([item.get("raw", {}) for item in recent_metrics] + [metrics])

    logger.info("Collected metrics:")
    logger.info(metrics)
    logger.info("Normalized metrics:")
    logger.info(normalized_metrics)
    logger.info("Aggregate metrics:")
    logger.info(aggregate)

    STORE.write_metrics(
        raw_metrics=metrics,
        normalized_metrics=normalized_metrics,
        aggregate=aggregate
    )

    alerts = check_metrics(metrics)

    if alerts:
        logger.warning(f"Critical alert detected: {alerts}")

    return {
        "raw": metrics,
        "normalized": normalized_metrics,
        "aggregate": aggregate,
        "alerts": alerts,
    }


if __name__ == "__main__":

    while True:
        try:
            collect_metrics()
        except Exception as e:
            logger.error(f"Error collecting metrics: {e}")

        time.sleep(30)