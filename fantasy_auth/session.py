from datetime import date
from espn_api.football import League
from espn_api.requests.espn_requests import ESPNAccessDenied
from .browser_login import get_espn_credentials
from .leagues import fetch_football_leagues, pick_league
from .storage import load_saved_credentials, save_credentials


def current_season():
    """NFL seasons start in September but belong to the year they begin in."""
    today = date.today()
    return today.year if today.month >= 3 else today.year - 1


def try_league(league_id, year, creds):
    """
    Try to connect with the given creds.
    Returns a League on success, or None if ESPN rejects the cookies.
    Other errors (network down, etc.) are NOT swallowed, so they don't
    trigger a pointless re-login.
    """
    try:
        return League(
            league_id=league_id,
            year=year,
            espn_s2=creds["espn_s2"],
            swid=creds["swid"],
        )
    except ESPNAccessDenied:
        return None


def ask_yes_no(prompt):
    while True:
        answer = input(f"{prompt} [y/n]: ").strip().lower()
        if answer in ("y", "yes"):
            return True
        if answer in ("n", "no"):
            return False


def get_league(year=None):
    """
    1. Try saved credentials + league id (no browser needed).
    2. If missing or expired, log in through the browser.
    3. Reuse the saved league id if there is one, otherwise discover
       the user's leagues and let them pick.
    4. Save on first login only if the user opts in; if they had saved
       credentials before, silently refresh the file.
    """
    year = year or current_season()

    saved = load_saved_credentials()
    had_saved = saved is not None
    saved_league_id = saved.get("league_id") if saved else None

    if saved and saved_league_id:
        league = try_league(saved_league_id, year, saved)
        if league:
            print("Using saved credentials.")
            return league
        print("Saved credentials have expired. Logging in again...")

    creds = get_espn_credentials()
    url_league_id = creds.pop("league_id_hint", None)

    league_id = saved_league_id
    if not league_id:
        leagues = fetch_football_leagues(creds)
        if leagues:
            league_id = pick_league(leagues)["league_id"]
        elif url_league_id:
            print(f"Using league id {url_league_id} detected from the browser URL.")
            league_id = url_league_id
        else:
            raise RuntimeError(
                "Couldn't find a league automatically. Log in again and open "
                "your league page (the URL should contain leagueId=...) before "
                "the tip countdown ends."
            )
    creds["league_id"] = league_id

    league = try_league(league_id, year, creds)
    if league is None:
        raise RuntimeError("ESPN rejected the new credentials. Try logging in again.")

    if had_saved:
        save_credentials(creds)  # user already opted in, just refresh
    elif ask_yes_no("Save credentials locally so you don't have to log in next time?"):
        save_credentials(creds)

    return league
