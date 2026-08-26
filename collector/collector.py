from __future__ import annotations

import time
from datetime import datetime, timezone

from detector.detector import check_metrics
from logger import logger

from collector.metrics import (
    get_cpu,
    get_memory,
    get_network,
    get_disk,
    get_highest_cpu_pod,
)

from collector.processing import (
    aggregate_metrics,
    normalize_metrics,
)

from storage import MetricsStore


# ============================================================
# STORAGE
# ============================================================

STORE = MetricsStore()


# ============================================================
# COLLECTION COUNTER
# ============================================================

collection_number = 0


# ============================================================
# BASELINE CALCULATION
# ============================================================

def calculate_baselines(
    recent_metrics: list[dict],
) -> dict[str, float]:

    cpu_values: list[float] = []
    memory_values: list[float] = []

    for item in recent_metrics:

        raw = item.get(
            "raw",
            item,
        )

        cpu = raw.get(
            "cpu_usage"
        )

        memory = raw.get(
            "memory_usage"
        )

        if cpu is not None:

            cpu_values.append(
                float(cpu)
            )

        if memory is not None:

            memory_values.append(
                float(memory)
            )

    baselines: dict[str, float] = {}

    if cpu_values:

        baselines["cpu"] = (
            sum(cpu_values)
            / len(cpu_values)
        )

    if memory_values:

        baselines["memory"] = (
            sum(memory_values)
            / len(memory_values)
        )

    return baselines


# ============================================================
# CLEAN METRICS
# ============================================================

def remove_none_values(
    metrics: dict,
) -> dict:

    return {
        key: value
        for key, value in metrics.items()
        if value is not None
    }


# ============================================================
# COLLECTION
# ============================================================

def collect_metrics():

    global collection_number

    collection_number += 1

    timestamp = datetime.now(
        timezone.utc
    ).strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    print(
        "\n" + "=" * 65,
        flush=True,
    )

    print(
        f"[{timestamp}] "
        f"Collection #{collection_number}",
        flush=True,
    )

    print(
        "=" * 65,
        flush=True,
    )

    # ========================================================
    # CPU
    # ========================================================

    cpu = get_cpu()

    # ========================================================
    # MEMORY
    # ========================================================

    memory = get_memory()

    # ========================================================
    # NETWORK
    # ========================================================

    network = get_network()

    # ========================================================
    # DISK
    # ========================================================

    try:

        disk = get_disk()

    except Exception as e:

        disk = None

        logger.error(
            "Unable to collect disk metric: %s",
            e,
        )

    # ========================================================
    # METRICS OBJECT
    # ========================================================

    metrics = {
        "cpu_usage": cpu,
        "memory_usage": memory,
        "network_usage": network,
        "disk_usage": disk,
    }

    disk_display = (
        f"{disk:.2f}%"
        if disk is not None
        else "N/A"
    )

    # ========================================================
    # POWERSHELL DISPLAY
    # ========================================================

    print(
        f"CPU={cpu:.2f}% | "
        f"MEM={memory:.2f}% | "
        f"NET={network:.2f} | "
        f"DISK={disk_display}",
        flush=True,
    )

    # ========================================================
    # NORMALIZATION
    # ========================================================

    metrics_for_processing = (
        remove_none_values(
            metrics
        )
    )

    normalized_metrics = (
        normalize_metrics(
            metrics_for_processing
        )
    )

    print(
        "Normalized: OK",
        flush=True,
    )

    # ========================================================
    # HISTORY
    # ========================================================

    recent_metrics = STORE.get_history(
        window="24h",
        limit=2880,
    )

    print(
        f"History loaded: "
        f"{len(recent_metrics)} records",
        flush=True,
    )

    # ========================================================
    # BASELINES
    # ========================================================

    baselines = calculate_baselines(
        recent_metrics
    )

    print(
        f"Baseline CPU="
        f"{baselines.get('cpu')} | "
        f"Baseline MEM="
        f"{baselines.get('memory')}",
        flush=True,
    )

    # ========================================================
    # AGGREGATION
    # ========================================================

    history_for_aggregation = []

    for item in recent_metrics:

        raw = item.get(
            "raw",
            {},
        )

        cleaned_raw = (
            remove_none_values(
                raw
            )
        )

        history_for_aggregation.append(
            cleaned_raw
        )

    current_for_aggregation = (
        remove_none_values(
            metrics
        )
    )

    aggregate = aggregate_metrics(
        history_for_aggregation
        + [
            current_for_aggregation
        ]
    )

    # ========================================================
    # STORAGE
    # ========================================================

    STORE.write_metric(
        {
            "timestamp": datetime.now(
                timezone.utc
            ),
            "cpu_usage": cpu,
            "memory_usage": memory,
            "network_usage": network,
            "disk_usage": disk,
        }
    )

    print(
        "Storage: OK",
        flush=True,
    )

    # ========================================================
    # HIGHEST CPU POD
    # ========================================================

    try:

        pod = get_highest_cpu_pod()

    except Exception as e:

        pod = None

        logger.error(
            "Unable to identify highest CPU pod: %s",
            e,
        )

    print(
        f"Pod principal: {pod}",
        flush=True,
    )

    # ========================================================
    # ANOMALY DETECTION
    # ========================================================

    alerts = check_metrics(
        metrics,
        service="infrastructure",
        pod=pod,
        baselines=baselines,
    )

    # ========================================================
    # ALERT DISPLAY
    # ========================================================

    if alerts:

        print(
            f"Anomaly: {alerts}",
            flush=True,
        )

        logger.warning(
            "Anomaly detected: %s",
            alerts,
        )

    else:

        print(
            "Anomaly: NORMAL",
            flush=True,
        )

    # ========================================================
    # LOGGING
    # ========================================================

    logger.info(
        "Metrics collected | "
        "CPU=%.2f MEM=%.2f NET=%.2f DISK=%s",
        cpu,
        memory,
        network,
        disk_display,
    )

    # ========================================================
    # RETURN
    # ========================================================

    return {
        "raw": metrics,
        "normalized": normalized_metrics,
        "aggregate": aggregate,
        "baselines": baselines,
        "pod": pod,
        "alerts": alerts,
    }


# ============================================================
# 30 SECOND COLLECTION LOOP
# ============================================================

COLLECTION_INTERVAL_SECONDS = 30


if __name__ == "__main__":

    print(
        "Monitoring Agent started"
    )

    print(
        "Collection interval: "
        f"{COLLECTION_INTERVAL_SECONDS} seconds"
    )

    next_run = time.monotonic()

    while True:

        try:

            collect_metrics()

        except KeyboardInterrupt:

            print(
                "\nMonitoring Agent stopped."
            )

            break

        except Exception as e:

            print(
                f"ERROR: {e}",
                flush=True,
            )

            logger.exception(
                "Error collecting metrics"
            )

        next_run += (
            COLLECTION_INTERVAL_SECONDS
        )

        sleep_time = max(
            0,
            next_run - time.monotonic(),
        )

        print(
            f"Next collection in "
            f"{sleep_time:.1f}s...",
            flush=True,
        )

        time.sleep(
            sleep_time
        )