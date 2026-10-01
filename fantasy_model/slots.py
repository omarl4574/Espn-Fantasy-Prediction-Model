"""Read the user's real starting-lineup requirements from their league settings."""

import requests

from .config import DEFAULT_LINEUP_SLOTS, POSITIONS

HOSTS = ["https://lm-api-reads.fantasy.espn.com", "https://fantasy.espn.com"]
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "application/json",
}

NON_STARTING = {"BE", "IR"}  # bench + injured reserve never score
OFFENSE = {"QB", "RB", "WR", "TE"}

# ESPN lineup-slot id -> name. Used only if espn_api's own constant can't be imported.
_FALLBACK_SLOT_NAMES = {
    0: "QB",
    1: "TQB",
    2: "RB",
    3: "RB/WR",
    4: "WR",
    5: "WR/TE",
    6: "TE",
    7: "OP",
    8: "DT",
    9: "DE",
    10: "LB",
    11: "DL",
    12: "CB",
    13: "S",
    14: "DB",
    15: "DP",
    16: "D/ST",
    17: "K",
    18: "P",
    19: "HC",
    20: "BE",
    21: "IR",
    23: "RB/WR/TE",
}


def _slot_id_names():
    """Prefer espn_api's own id->name table so names match Player.eligibleSlots."""
    try:
        from espn_api.football.constant import POSITION_MAP

        names = {
            k: v
            for k, v in POSITION_MAP.items()
            if isinstance(k, int) and isinstance(v, str)
        }
        if names:
            return names
    except Exception:
        pass
    return _FALLBACK_SLOT_NAMES


def slot_accepts(slot, position):
    """Can a player at `position` fill a slot with this name?"""
    if slot == position:
        return True
    if slot == "OP":  # offensive player (superflex)
        return position in OFFENSE
    if slot == "TQB":
        return position == "QB"
    if "/" in slot and slot != "D/ST":  # combo slots like RB/WR/TE, WR/TE, RB/WR
        return position in slot.split("/")
    return False


def positions_in_use(slots):
    """Supported positions that can actually start somewhere in this league."""
    return [
        position
        for position in POSITIONS
        if any(slot_accepts(slot, position) for slot in slots)
    ]


def _get_settings_json(league_id, year, creds):
    """Raw mSettings response for this league, or None."""
    for host in HOSTS:
        url = f"{host}/apis/v3/games/ffl/seasons/{year}/segments/0/leagues/{league_id}"
        try:
            resp = requests.get(
                url,
                params={"view": "mSettings"},
                cookies={"SWID": creds["swid"], "espn_s2": creds["espn_s2"]},
                headers=HEADERS,
                timeout=15,
            )
            resp.raise_for_status()
            return resp.json()
        except (requests.RequestException, ValueError):
            continue
    return None


def fetch_lineup_slots(league_id, year, creds):
    """{slot_name: count} for starting slots, or None if it can't be fetched."""
    data = _get_settings_json(league_id, year, creds)
    try:
        counts = data["settings"]["rosterSettings"]["lineupSlotCounts"]
    except (KeyError, TypeError):
        return None

    names = _slot_id_names()
    slots = {}
    for sid, n in counts.items():
        try:
            name = names.get(int(sid))
        except (TypeError, ValueError):
            continue
        if name and int(n) > 0 and name not in NON_STARTING:
            slots[name] = int(n)
    return slots or None


RECEPTIONS_STAT_ID = 53  # ESPN stat id for receptions (verify with --inspect)


def fetch_reception_points(league_id, year, creds):
    """Points per reception in this league (0 / 0.5 / 1 ...), or None if unknown."""
    data = _get_settings_json(league_id, year, creds)
    try:
        items = data["settings"]["scoringSettings"]["scoringItems"]
    except (KeyError, TypeError):
        return None
    for item in items:
        if item.get("statId") == RECEPTIONS_STAT_ID:
            return float(item.get("points", 0.0))
    return 0.0  # no reception item listed => standard scoring


def get_lineup_slots(league, creds):
    """Auto-detect this league's lineup; fall back to defaults with a loud warning."""
    slots = fetch_lineup_slots(league.league_id, league.year, creds)
    if slots is None:
        print(
            "WARNING: couldn't read this league's lineup settings; using defaults "
            f"{DEFAULT_LINEUP_SLOTS}. Recommendations may not match your league."
        )
        slots = dict(DEFAULT_LINEUP_SLOTS)
    else:
        print(f"Detected lineup slots: {slots}")

    unsupported = [
        slot
        for slot in slots
        if not any(slot_accepts(slot, position) for position in POSITIONS)
    ]
    if unsupported:
        print(
            f"WARNING: slots {unsupported} (e.g. IDP) aren't supported by the models yet "
            "and will be treated as empty."
        )
    return slots
