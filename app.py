from flask import Flask

from api import metrics_api
from api.approvals import approvals_api
from api.dashboard import dashboard_api


def create_app() -> Flask:
    app = Flask(__name__)
    app.register_blueprint(metrics_api)
    app.register_blueprint(approvals_api)
    app.register_blueprint(dashboard_api)
    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)