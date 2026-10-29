from flask import Flask

from .routes import bp
from .state import AnalysisState


def create_app(league, creds, my_team_id):
    app = Flask(__name__)
    app.config["STATE"] = AnalysisState(league, creds, my_team_id)
    app.register_blueprint(bp)
    return app
