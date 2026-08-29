from flask import Flask

from api import metrics_api
from api.approvals import approvals_api
from api.dashboard import dashboard_api
from monitor_loop import start_background_monitor


def create_app() -> Flask:
    app = Flask(__name__)
    app.register_blueprint(metrics_api)
    app.register_blueprint(approvals_api)
    app.register_blueprint(dashboard_api)
    return app


app = create_app()

# Démarre la boucle de surveillance autonome (thread daemon) : sans cet
# appel, monitor_loop.py n'est jamais exécuté et aucune remédiation
# automatique ne se déclenche, même si Prometheus/le dashboard
# détectent bien les métriques et incidents.
start_background_monitor()


if __name__ == "__main__":
    # use_reloader=False : le reloader Werkzeug surveille les fichiers et
    # relance le process au moindre changement détecté sous /app — inutile
    # ici et risqué si une requête écrit un fichier (ex: modèle ML) pendant
    # son traitement.
    app.run(host="0.0.0.0", port=5000, debug=True, use_reloader=False)