from flask import Blueprint, jsonify, request

from collector.processing import aggregate_metrics
from storage import MetricsStore


metrics_api = Blueprint("metrics_api", __name__)
store = MetricsStore()


@metrics_api.get("/health")
def health():
	return jsonify(
		{
			"status": "ok",
			"storage": "influxdb" if store.influx_enabled else "local-jsonl-fallback",
			"retention_days": store.retention_days,
		}
	)


@metrics_api.get("/metrics/latest")
def latest_metrics():
	latest = store.get_latest()
	if latest is None:
		return jsonify({"message": "No metrics available yet."}), 404
	return jsonify(latest)


@metrics_api.get("/metrics/history")
def metrics_history():
	window = request.args.get("window", "24h")
	limit = int(request.args.get("limit", "100"))
	return jsonify(store.get_history(window=window, limit=limit))


@metrics_api.get("/metrics/stats")
def metrics_stats():
	window = request.args.get("window", "24h")
	history = store.get_history(window=window, limit=5000)
	if not history:
		return jsonify({"message": "No metrics available yet."}), 404

	aggregates = aggregate_metrics(item.get("raw", {}) for item in history)
	return jsonify(
		{
			"window": window,
			"count": len(history),
			"aggregate": aggregates,
		}
	)

