from __future__ import annotations

import os
import time
from datetime import datetime, timezone

from collector.metrics import (
    get_cpu,
    get_memory,
    get_network,
    get_disk,
    get_highest_cpu_pod,
)
from collector.processing import aggregate_metrics, normalize_metrics
from detector.pipeline import check_and_confirm
from logger import logger
from orchestrator.orchestrator import handle_alert
from storage import MetricsStore

STORE = MetricsStore()

COLLECTION_INTERVAL_SECONDS = int(os.getenv("COLLECTION_INTERVAL_SECONDS", "30"))
DRY_RUN = os.getenv("DRY_RUN", "false").lower() in {"1", "true", "yes", "on"}
AUTO_REMEDIATION_ENABLED = os.getenv(
    "AUTO_REMEDIATION_ENABLED", "true"
).lower() in {"1", "true", "yes", "on"}
K8S_NAMESPACE = os.getenv("K8S_NAMESPACE", "default")

collection_number = 0


def calculate_baselines(recent_metrics: list[dict]) -> dict[str, float]:
    cpu_values: list[float] = []
    memory_values: list[float] = []

    for item in recent_metrics:
        raw = item.get("raw", item)
        if raw.get("cpu_usage") is not None:
            cpu_values.append(float(raw["cpu_usage"]))
        if raw.get("memory_usage") is not None:
            memory_values.append(float(raw["memory_usage"]))

    result: dict[str, float] = {}
    if cpu_values:
        result["cpu"] = sum(cpu_values) / len(cpu_values)
    if memory_values:
        result["memory"] = sum(memory_values) / len(memory_values)
    return result


def _clean(metrics: dict) -> dict:
    return {k: v for k, v in metrics.items() if v is not None}


def collect_metrics() -> dict:
    global collection_number
    collection_number += 1

    now = datetime.now(timezone.utc)
    timestamp = now.strftime("%Y-%m-%d %H:%M:%S")

    print("\n" + "=" * 70, flush=True)
    print(f"[{timestamp}] Collection #{collection_number}", flush=True)
    print("=" * 70, flush=True)

    cpu = float(get_cpu())
    memory = float(get_memory())
    network = float(get_network())

    try:
        disk = get_disk()
    except Exception as exc:
        disk = None
        logger.warning("Disk collection failed: %s", exc)

    metrics = {
        "cpu_usage": cpu,
        "memory_usage": memory,
        "network_usage": network,
        "disk_usage": disk,
    }

    print(
        f"CPU={cpu:.2f}% | MEM={memory:.2f}% | "
        f"NET={network:.2f} | DISK={disk if disk is not None else 'N/A'}",
        flush=True,
    )

    recent = STORE.get_history(window="24h", limit=2880)
    baselines = calculate_baselines(recent)

    history_for_aggregation = [
        _clean(item.get("raw", {})) for item in recent
    ]
    aggregate = aggregate_metrics(history_for_aggregation + [_clean(metrics)])

    STORE.write_metric(
        {
            "timestamp": now,
            "cpu_usage": cpu,
            "memory_usage": memory,
            "network_usage": network,
            "disk_usage": disk,
        }
    )

    pod = os.getenv("TARGET_POD")
    target_namespace = K8S_NAMESPACE

    if not pod:
        try:
            discovered = get_highest_cpu_pod()
            if discovered and "/" in discovered:
                discovered_namespace, discovered_pod = discovered.split("/", 1)
                target_namespace = discovered_namespace or K8S_NAMESPACE
                pod = discovered_pod
            else:
                pod = discovered
        except Exception as exc:
            logger.warning("Unable to identify highest CPU pod: %s", exc)

    if not pod:
        # Safe demo fallback: choose a running pod in the configured namespace.
        # Set TARGET_POD explicitly in production to avoid ambiguity.
        try:
            import json
            import subprocess

            raw = subprocess.check_output(
                [
                    "kubectl",
                    "--kubeconfig",
                    os.getenv("KUBECONFIG", ""),
                    "-n",
                    K8S_NAMESPACE,
                    "get",
                    "pods",
                    "-o",
                    "json",
                ],
                text=True,
                timeout=15,
            )
            pod_items = json.loads(raw).get("items", [])
            running = [
                item["metadata"]["name"]
                for item in pod_items
                if item.get("status", {}).get("phase") == "Running"
            ]
            pod = running[0] if running else None
        except Exception as exc:
            logger.warning("Kubernetes target-pod fallback failed: %s", exc)

    print(
        f"Target pod: {pod} | namespace: {target_namespace}",
        flush=True,
    )

    # Stage 1: thresholds/duration/trend
    # Stage 2: ML confirmation + severity
    alerts = check_and_confirm(
        _clean(metrics),
        service="infrastructure",
        baselines=baselines,
    )

    if not alerts:
        print("Anomaly: NORMAL", flush=True)
    else:
        print(f"Confirmed incidents: {len(alerts)}", flush=True)

        for alert in alerts:
            alert["pod"] = alert.get("pod") or pod
            alert["namespace"] = target_namespace

            print(
                "🚨 INCIDENT DETECTED | "
                f"metric={alert.get('metric')} "
                f"value={alert.get('value')} "
                f"threshold={alert.get('threshold')} "
                f"severity={alert.get('severity')} "
                f"ml_score={alert.get('ml_score')}",
                flush=True,
            )

            if not AUTO_REMEDIATION_ENABLED:
                print("AUTO_REMEDIATION_ENABLED=false -> incident only", flush=True)
                continue

            try:
                result = handle_alert(
                    alert=alert,
                    pod=alert.get("pod"),
                    namespace=target_namespace,
                    dry_run=DRY_RUN,
                )
                print(
                    "🤖 ORCHESTRATOR RESULT | "
                    f"incident={result.get('incident_id')} "
                    f"outcome={result.get('outcome')} "
                    f"reason={result.get('reason', '')}",
                    flush=True,
                )
            except Exception:
                logger.exception("End-to-end incident processing failed")

    return {
        "raw": metrics,
        "normalized": normalize_metrics(_clean(metrics)),
        "aggregate": aggregate,
        "baselines": baselines,
        "pod": pod,
        "alerts": alerts,
    }


if __name__ == "__main__":
    print("Monitoring Agent started", flush=True)
    print(
        f"Interval={COLLECTION_INTERVAL_SECONDS}s | "
        f"DRY_RUN={DRY_RUN} | "
        f"AUTO_REMEDIATION_ENABLED={AUTO_REMEDIATION_ENABLED}",
        flush=True,
    )

    next_run = time.monotonic()
    while True:
        try:
            collect_metrics()
        except KeyboardInterrupt:
            print("Monitoring Agent stopped.", flush=True)
            break
        except Exception:
            logger.exception("Error in monitoring loop")

        next_run += COLLECTION_INTERVAL_SECONDS
        time.sleep(max(0, next_run - time.monotonic()))
