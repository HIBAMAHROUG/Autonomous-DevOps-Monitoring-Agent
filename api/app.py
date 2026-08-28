# api/app.py
from flask import Flask, jsonify, request
from flask_cors import CORS
import os
import json
from datetime import datetime
from api.dashboard import dashboard_api
from api.approvals import approvals_api
from api.routes import metrics_api

app = Flask(__name__, template_folder=os.path.join(os.path.dirname(__file__), '..', 'templates'))
CORS(app)
app.register_blueprint(dashboard_api)
app.register_blueprint(approvals_api)
app.register_blueprint(metrics_api)

# Données simulées pour la démo
METRICS_DATA = [
    {"metric": "cpu_usage", "value": 45.2, "unit": "%", "timestamp": datetime.now().isoformat()},
    {"metric": "memory_usage", "value": 62.8, "unit": "%", "timestamp": datetime.now().isoformat()},
    {"metric": "network_io", "value": 1024, "unit": "KB/s", "timestamp": datetime.now().isoformat()},
    {"metric": "disk_usage", "value": 78.5, "unit": "%", "timestamp": datetime.now().isoformat()},
    {"metric": "pod_count", "value": 12, "unit": "pods", "timestamp": datetime.now().isoformat()}
]

AUDIT_DATA = [
    {"id": 1, "action": "restart_pod", "target": "nginx-pod", "status": "success", "timestamp": "2026-08-21T14:25:00"},
    {"id": 2, "action": "scale_deployment", "target": "web-app", "status": "pending", "timestamp": "2026-08-21T14:20:00"},
    {"id": 3, "action": "delete_pod", "target": "test-pod", "status": "success", "timestamp": "2026-08-21T14:15:00"},
    {"id": 4, "action": "rollback", "target": "api-v2", "status": "success", "timestamp": "2026-08-21T14:10:00"}
]

# ==================== ROUTES ====================

@app.route('/')
def home():
    """Liste tous les endpoints disponibles"""
    return jsonify({
        "service": "DevOps Monitoring Agent",
        "version": "1.0.0",
        "status": "operational",
        "endpoints": [
            "/",
            "/api/health",
            "/api/metrics",
            "/api/audit",
            "/api/approvals",
            "/api/approvals/pending",
            "/api/approvals/<action_id>/decide",
            "/api/safety/check",
            "/api/security/kill-switch",
            "/api/security/circuit-breaker"
        ]
    })

@app.route('/api/health')
def health():
    """Vérification de l'état de santé"""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "services": {
            "api": "running",
            "prometheus": "connected",
            "loki": "connected",
            "influxdb": "connected"
        }
    })

@app.route('/api/status')
def status():
    """État détaillé de l'agent"""
    return jsonify({
        "service": "DevOps Monitoring Agent",
        "status": "operational",
        "version": "1.0.0",
        "uptime": "2 hours",
        "metrics_collected": 156,
        "incidents_detected": 12,
        "auto_repaired": 10,
        "pending_approvals": 1,
        "timestamp": datetime.now().isoformat()
    })

@app.route('/api/metrics')
def metrics():
    """Récupère les métriques en temps réel"""
    # Ajouter la possibilité de filtrer
    metric_type = request.args.get('type', 'all')
    
    if metric_type == 'cpu':
        return jsonify([m for m in METRICS_DATA if 'cpu' in m['metric']])
    elif metric_type == 'memory':
        return jsonify([m for m in METRICS_DATA if 'memory' in m['metric']])
    else:
        return jsonify(METRICS_DATA)

@app.route('/api/audit')
def audit():
    """Historique des actions"""
    # Filtrer par type d'action
    action_filter = request.args.get('action', 'all')
    
    if action_filter != 'all':
        filtered = [a for a in AUDIT_DATA if a['action'] == action_filter]
        return jsonify(filtered)
    return jsonify(AUDIT_DATA)

@app.route('/api/approvals')
def approvals():
    """Toutes les approbations"""
    return jsonify([
        {"id": 1, "action": "scale_deployment", "target": "web-app", "status": "pending", "requested_by": "agent", "timestamp": "2026-08-21T14:20:00"},
        {"id": 2, "action": "delete_pod", "target": "database-pod", "status": "approved", "requested_by": "agent", "timestamp": "2026-08-21T13:50:00"},
        {"id": 3, "action": "restart_service", "target": "api-gateway", "status": "rejected", "requested_by": "agent", "timestamp": "2026-08-21T13:30:00"}
    ])

@app.route('/api/approvals/pending')
def pending_approvals():
    """Approbations en attente uniquement"""
    return jsonify([
        {"id": 1, "action": "scale_deployment", "target": "web-app", "requested_by": "agent", "timestamp": "2026-08-21T14:20:00"}
    ])

@app.route('/api/approvals/<int:action_id>/decide', methods=['POST'])
def decide_approval(action_id):
    """Décider d'une approbation (POST)"""
    data = request.get_json()
    decision = data.get('decision')  # 'approve' ou 'reject'
    
    if decision == 'approve':
        return jsonify({"status": "approved", "message": f"Action {action_id} approuvée"})
    elif decision == 'reject':
        return jsonify({"status": "rejected", "message": f"Action {action_id} rejetée"})
    else:
        return jsonify({"error": "Décision invalide"}), 400

@app.route('/api/safety/check')
def safety_check():
    """Vérifier les garde-fous de sécurité"""
    return jsonify({
        "rate_limit": {
            "enabled": True,
            "max_actions": 3,
            "window_seconds": 900,
            "current_actions": 2
        },
        "circuit_breaker": {
            "status": "closed",
            "failures": 0,
            "threshold": 5,
            "reset_timeout": 60
        },
        "human_in_the_loop": {
            "enabled": True,
            "critical_actions": ["delete_pod", "scale_deployment"],
            "pending_approvals": 1
        },
        "kill_switch": {
            "enabled": True,
            "status": "normal",
            "emergency_stop": False
        },
        "blast_radius": {
            "max_pods_per_action": 3,
            "limit_enforced": True
        }
    })

@app.route('/api/security/circuit-breaker')
def circuit_breaker():
    """État du circuit breaker"""
    return jsonify({
        "status": "closed",
        "threshold": 5,
        "current_failures": 0,
        "last_failure": None,
        "reset_timeout": 60,
        "state": "normal"
    })

@app.route('/api/security/kill-switch')
def kill_switch():
    """État du kill switch"""
    return jsonify({
        "status": "enabled",
        "mode": "normal",
        "emergency_stop": False,
        "activated_by": None,
        "activated_at": None
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)


