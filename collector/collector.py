import time
from datetime import datetime

from detector.detector import check_metrics
from logger import logger

from collector.metrics import (
    get_cpu,
    get_memory,
    get_network,
    get_disk,
)

from collector.processing import (
    aggregate_metrics,
    normalize_metrics,
)

from storage import MetricsStore


STORE = MetricsStore()


def collect_metrics():
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    print(f"\n[{timestamp}] Collection started", flush=True)

    cpu = get_cpu()
    memory = get_memory()
    network = get_network()
    disk = get_disk()

    metrics = {
        "cpu_usage": cpu,
        "memory_usage": memory,
        "network_usage": network,
        "disk_usage": disk,
    }

    print(
        f"CPU={cpu:.2f}% | "
        f"MEM={memory:.2f}% | "
        f"NET={network:.2f} | "
        f"DISK={disk:.2f}%",
        flush=True,
    )

    normalized_metrics = normalize_metrics(metrics)
    print("Normalized: OK", flush=True)

    recent_metrics = STORE.list_metrics(limit=60)

    aggregate = aggregate_metrics(
        [item.get("raw", {}) for item in recent_metrics] + [metrics]
    )

    STORE.write_metrics(
        raw_metrics=metrics,
        normalized_metrics=normalized_metrics,
        aggregate=aggregate,
    )

    print("Storage: OK", flush=True)

    alerts = check_metrics(metrics)

    if alerts:
        print(f"Anomaly: {alerts}", flush=True)
        logger.warning("Anomaly detected: %s", alerts)
    else:
        print("Anomaly: NORMAL", flush=True)

    logger.info(
        "Metrics collected | CPU=%.2f MEM=%.2f NET=%.2f DISK=%.2f",
        cpu,
        memory,
        network,
        disk,
    )

    return {
        "raw": metrics,
        "normalized": normalized_metrics,
        "aggregate": aggregate,
        "alerts": alerts,
    }


if __name__ == "__main__":
    print("Monitoring Agent started")
    print("Collection interval: 30 seconds")

    while True:
        try:
            collect_metrics()

        except KeyboardInterrupt:
            print("\nMonitoring Agent stopped.")
            break

        except Exception as e:
            print(f"ERROR: {e}", flush=True)
            logger.exception("Error collecting metrics")

        print("Next collection in 30s...", flush=True)
        time.sleep(30)
