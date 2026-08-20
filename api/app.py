from flask import Flask
from dotenv import load_dotenv

from api.routes import metrics_api

load_dotenv()


def create_app():
 app = Flask(name)

 # Les routes contiennent deja le prefixe /api
 app.register_blueprint(metrics_api)

 return app


app = create_app()


if name == "main":
 app.run(host="0.0.0.0", port=5000, debug=False)
