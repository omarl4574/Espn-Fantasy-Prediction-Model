"""
User-editable settings: defaults come from config.py, overrides are saved to
~/.espn_fantasy/settings.json (no secrets in it). Used by the CLI and the website.
"""
import json
from pathlib import Path

from . import config

SETTINGS_FILE = Path.home() / ".espn_fantasy" / "settings.json"

SETTING_SPECS = [
    dict(key="min_pickup_gain", label="Minimum pickup gain", group="Drop / add",
         type="float", default=config.MIN_PICKUP_GAIN, min=0, max=500, step=0.5,
         help="Only suggest a swap that improves your lineup by at least this many rest-of-season points."),
    dict(key="dropadd_results", label="Suggestions to show", group="Drop / add",
         type="int", default=10, min=1, max=25, step=1,
         help="Maximum number of drop/add suggestions."),

    dict(key="max_trade_size", label="Max players per side", group="Trades",
         type="int", default=config.MAX_TRADE_SIZE, min=1, max=3, step=1,
         help="3-for-3 searches are MUCH slower (can take many minutes). 2 is a good default."),
    dict(key="min_my_gain", label="Minimum gain for you", group="Trades",
         type="float", default=config.MIN_MY_GAIN, min=0, max=500, step=0.5,
         help="A trade must improve your best lineup by at least this much."),
    dict(key="their_tolerance", label="Max loss for them", group="Trades",
         type="float", default=config.THEIR_TOLERANCE, min=0, max=500, step=0.5,
         help="How much the other team's lineup may drop. Lower = fairer-looking trades."),
    dict(key="min_value_ratio", label="Min value ratio", group="Trades",
         type="float", default=config.MIN_VALUE_RATIO, min=0.5, max=1.5, step=0.01,
         help="Value they receive / value they give must be at least this. 1.0 = perfectly even on paper."),
    dict(key="trade_results", label="Trade ideas to show", group="Trades",
         type="int", default=10, min=1, max=25, step=1,
         help="Maximum number of trade ideas."),

    dict(key="n_external_seasons", label="Extra NFL seasons", group="Model & data",
         type="int", default=config.N_EXTERNAL_SEASONS, min=0, max=10, step=1,
         help="Past seasons of NFL stats to download for training. 0 = use only your league's ESPN data."),
    dict(key="external_weight", label="Extra-data weight", group="Model & data",
         type="float", default=config.EXTERNAL_WEIGHT, min=0.1, max=1.0, step=0.05,
         help="How much downloaded NFL rows count compared with your league's own data."),
]


def defaults():
    return {spec["key"]: spec["default"] for spec in SETTING_SPECS}


def validate(values, base=None):
    """Return (clean_values, errors). Missing keys keep their value from `base`."""
    base = base if base is not None else defaults()
    clean, errors = {}, {}
    for spec in SETTING_SPECS:
        key = spec["key"]
        raw = values.get(key, base.get(key, spec["default"]))
        try:
            number = float(raw)
            if spec["type"] == "int":
                if number != int(number):
                    raise ValueError
                number = int(number)
        except (TypeError, ValueError):
            errors[key] = "Must be a whole number" if spec["type"] == "int" else "Must be a number"
            continue
        if not spec["min"] <= number <= spec["max"]:
            errors[key] = f"Must be between {spec['min']} and {spec['max']}"
            continue
        clean[key] = number
    return clean, errors


def load_settings():
    """Defaults overlaid with any valid saved overrides."""
    merged = defaults()
    try:
        with open(SETTINGS_FILE, "r") as f:
            saved = json.load(f)
        for key, value in saved.items():
            if key in merged:
                clean, errors = validate({key: value}, base=merged)
                if key not in errors:
                    merged[key] = clean[key]
    except (FileNotFoundError, json.JSONDecodeError, AttributeError):
        pass
    return merged


def save_settings(clean):
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(SETTINGS_FILE, "w") as f:
        json.dump(clean, f, indent=2)


def reset_settings():
    try:
        SETTINGS_FILE.unlink()
    except FileNotFoundError:
        pass
    return defaults()
