from flask import Blueprint, current_app, jsonify, render_template, request

from fantasy_models.settings import (
    SETTING_SPECS, defaults, load_settings, reset_settings, save_settings, validate,
)

bp = Blueprint("main", __name__)


def _state():
    return current_app.config["STATE"]


@bp.get("/")
def index():
    return render_template("index.html")


@bp.get("/api/status")
def status():
    return jsonify(_state().snapshot())


@bp.get("/api/data")
def data():
    result = _state().result
    if result is None:
        return jsonify({"ready": False})
    return jsonify({"ready": True, **result})


@bp.post("/api/reload")
def reload_models():
    """Re-download league data, retrain the model, and apply the saved settings."""
    started = _state().start(load_settings(), refresh=True)
    return jsonify({"started": started}), (202 if started else 409)


@bp.get("/api/settings")
def get_settings():
    return jsonify({"specs": SETTING_SPECS, "values": load_settings(), "defaults": defaults()})


@bp.post("/api/settings")
def update_settings():
    payload = request.get_json(silent=True) or {}
    clean, errors = validate(payload, base=load_settings())
    if errors:
        return jsonify({"ok": False, "errors": errors}), 400
    save_settings(clean)
    return jsonify({"ok": True, "values": clean})


@bp.post("/api/settings/reset")
def reset():
    return jsonify({"ok": True, "values": reset_settings()})
