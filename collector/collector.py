import time
from detector.detector import check_metrics
from logger import logger
from collector.metrics import (
    get_cpu,
    get_memory,
    get_network,
    get_disk
)


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

    logger.info("Collected metrics:")
    logger.info(metrics)

    alerts = check_metrics(metrics)

    if alerts:
        logger.warning(f"Critical alert detected: {alerts}")

    print(metrics)


if __name__ == "__main__":

    while True:
        try:
            collect_metrics()
        except Exception as e:
            logger.error(f"Error collecting metrics: {e}")

        time.sleep(30)