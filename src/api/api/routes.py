import os
from flask import Blueprint, request, jsonify, current_app
from storage.metrics_store import MetricsStore

metrics_api = Blueprint('metrics_api', __name__)

# Initialisation du store
store = MetricsStore()

@metrics_api.route('/api/health', methods=['GET'])
def health():
    """Vérifie l'état du service et du stockage."""
    health_status = store.health_check()
    
    return jsonify({
        "status": health_status.get("status", "ok"),
        "storage": health_status.get("storage", "unknown"),
        "retention_days": store.retention_days,
        "bucket": store.bucket,
        "org": store.org
    })

@metrics_api.route('/api/metrics', methods=['POST'])
def post_metrics():
    """Reçoit et stocke des métriques."""
    # Vérification de l'API Key
    api_key = request.headers.get('X-API-Key')
    if not api_key or api_key != os.getenv('API_KEY'):
        return jsonify({"error": "Unauthorized"}), 401
    
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400
    
    try:
        store.write_metric(data)
        return jsonify({"message": "Metric stored successfully"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@metrics_api.route('/api/metrics/history', methods=['GET'])
def get_metrics_history():
    """Récupère l'historique des métriques."""
    # Vérification de l'API Key
    api_key = request.headers.get('X-API-Key')
    if not api_key or api_key != os.getenv('API_KEY'):
        return jsonify({"error": "Unauthorized"}), 401
    
    window = request.args.get('window', '1h')
    limit = request.args.get('limit', 100, type=int)
    
    try:
        history = store.get_history(window=window, limit=limit)
        return jsonify({
            "window": window,
            "limit": limit,
            "count": len(history),
            "metrics": history
        })
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@metrics_api.route('/api/metrics/latest', methods=['GET'])
def get_latest_metric():
    """Récupère la dernière métrique."""
    # Vérification de l'API Key
    api_key = request.headers.get('X-API-Key')
    if not api_key or api_key != os.getenv('API_KEY'):
        return jsonify({"error": "Unauthorized"}), 401
    
    try:
        latest = store.get_latest()
        if latest:
            return jsonify(latest)
        else:
            return jsonify({"message": "No metrics available yet."}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500
