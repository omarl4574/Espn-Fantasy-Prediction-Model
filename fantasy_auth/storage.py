import json
import os
from pathlib import Path

CREDS_FILE = Path.home() / "espn_fantasy" / "credentials.json"


def load_saved_credentials():
    """Return saved dict (swid, espn_s2, league_id), or None if missing/corrupt."""

    try:
        with open(CREDS_FILE, "r") as f:
            creds = json.load(f)
        if creds.get("swid") and creds.get("espn_s2"):
            return creds
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    return None


def save_credentials(creds):
    """Write credentials to disk, readable only by current user."""
    CREDS_FILE.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(CREDS_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(creds, f)
    print(f"Credentials saved to {CREDS_FILE}. Keep this file secure!")


def delete_saved_credentials():
    try:
        CREDS_FILE.unlink()
        print(f"Deleted saved credentials at {CREDS_FILE}.")
    except FileNotFoundError:
        print(f"No saved credentials found at {CREDS_FILE}.")
