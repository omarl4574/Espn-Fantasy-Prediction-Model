import json
from urllib.parse import quote

import requests

FAN_API = "https://fan.api.espn.com/apis/v2/fans/{swid}"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "application/json",
}

# Try the fuller request first, then a bare one, in case ESPN trims results
# depending on the parameters.
PARAM_VARIANTS = [
    {
        "displayEvents": "true",
        "displayNow": "true",
        "displayRecs": "true",
        "recLimit": "5",
        "context": "fantasy",
        "source": "ESPN.com+-+FAM",
        "lang": "en",
        "section": "espn",
        "region": "us",
    },
    {},
]


def _request(creds, params):
    swid = creds["swid"]
    resp = requests.get(
        FAN_API.format(swid=quote(swid, safe="")),
        params=params,
        headers=HEADERS,
        cookies={"SWID": swid, "espn_s2": creds["espn_s2"]},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def _is_football(pref, entry):
    """Deliberately loose: any one football signal is enough."""
    if str(entry.get("abbrev", "")).lower() == "ffl":
        return True
    if entry.get("gameId") == 1:
        return True
    return "/football/" in json.dumps(pref).lower()


def _parse_leagues(data):
    leagues = []
    for pref in data.get("preferences", []):
        entry = (pref.get("metaData") or {}).get("entry") or {}
        team_name = (entry.get("entryMetadata") or {}).get("teamName")
        is_football = _is_football(pref, entry)
        for group in entry.get("groups", []):
            if group.get("groupId") is None:
                continue
            leagues.append(
                {
                    "league_id": group.get("groupId"),
                    "name": group.get("groupName"),
                    "year": entry.get("seasonId"),
                    "team_name": team_name,
                    "is_football": is_football,
                }
            )
    return leagues


def describe_structure(data):
    """
    Print the SHAPE of the response (keys only, no cookie values or IDs)
    so it's safe to copy/paste when debugging.
    """
    prefs = data.get("preferences", [])
    print("  Top-level keys:", list(data.keys()))
    print("  Number of preferences:", len(prefs))
    for i, pref in enumerate(prefs[:10]):
        entry = (pref.get("metaData") or {}).get("entry") or {}
        print(
            f"  [{i}] pref keys={list(pref.keys())} "
            f"entry keys={list(entry.keys())} "
            f"abbrev={entry.get('abbrev')} gameId={entry.get('gameId')} "
            f"groups={len(entry.get('groups', []))}"
        )


def fetch_football_leagues(creds, debug=False):
    """
    Ask ESPN which fantasy leagues this account belongs to.
    Returns a list of dicts: {league_id, name, year, team_name, is_football}.
    Returns [] (and prints diagnostics) if nothing is found.

    NOTE: undocumented endpoint, so failures are reported rather than raised.
    """
    last_data = None
    for params in PARAM_VARIANTS:
        try:
            data = _request(creds, params)
        except (requests.RequestException, ValueError) as e:
            print(f"League lookup request failed: {e}")
            continue

        last_data = data
        if debug:
            print(json.dumps(data, indent=2)[:5000])

        leagues = _parse_leagues(data)
        if leagues:
            return leagues

    print("No leagues found via ESPN's fan API. Response structure:")
    if last_data is not None:
        describe_structure(last_data)
    return []


def pick_league(leagues):
    """Auto-select if there's only one league, otherwise let the user choose."""
    football = [lg for lg in leagues if lg["is_football"]]
    candidates = football or leagues  # if detection failed, show everything

    if not candidates:
        raise RuntimeError("No leagues available to pick from.")
    if len(candidates) == 1:
        return candidates[0]

    print("Multiple leagues found:")
    for i, lg in enumerate(candidates, 1):
        print(f"  {i}. {lg['name']} (team: {lg['team_name']}, season {lg['year']})")

    while True:
        choice = input("Pick a league number: ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(candidates):
            return candidates[int(choice) - 1]
