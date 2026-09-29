# Reads the users real starting-lineup requirements from their fantasy league settings

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

NON_STARTING = {"BE", "IR"}

OFFENSE = {"QB", "RB", "WR", "TE"}

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
    22: "RB/WR/TE",
}


def _slot_id_names():
    """Perfer espn_api's own id->name table so names match Player.eligibileSlots"""

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


def slots_accepts(slot, position):
    """Can a player at position fill a slot with this name"""

    if slot == position:
        return True
    if slot == "OP":
        # offensive player (superflex)
        return position in OFFENSE
    if slot == "TQB":
        return position == "QB"
    if "/" in slot and slot != "D/ST":
        # flex slot like RB/WR/TE or WR/TE
        return position in slot.split("/")

    return False


def positions_in_use(slots):
    """Supported positions that can actually start somewhere in this league"""
    return [p for p in POSITIONS if any(slots_accepts(s, p) for s in slots)]


def fetch_lineup_slots(league_id, year, creds):
    """{slot_name: count} for starting slots or None if it can't be fetched"""

    names = _slot_id_names()
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
            counts = resp.json()["settings"]["lineupSlotCounts"]
        except (requests.exceptions.RequestException, ValueError, KeyError):
            continue

        slots = {}
        for sid, n in counts.items():
            try:
                name = names.get(int(sid))
            except (TypeError, ValueError):
                continue

            if name and int(n) > 0 and name not in NON_STARTING:
                slots[name] = int(n)
        if slots:
            return slots

        return None


def get_lineup_slots(league, creds):
    """Return the starting lineup slots for a league, or default if it can't be fetched with a warning"""

    slots = fetch_lineup_slots(league.league_id, league.year, creds)

    if slots is None:
        print(
            "Warning: couldn't read this league's lineup slots, using default instead. "
            f"{DEFAULT_LINEUP_SLOTS}. Recommendations may not match your league"
        )
        slots = dict(DEFAULT_LINEUP_SLOTS)
    else:
        print(f"Detected league lineup slots: {slots}")

    unsupported = [s for s in slots if not any(slots_accepts(s, p) for p in POSITIONS)]
    if unsupported:
        print(
            f"Warning: league has unsupported lineup slots: {unsupported}."
            "These slots are not supported by this model yet and will be treated as empty."
        )

    return slots
