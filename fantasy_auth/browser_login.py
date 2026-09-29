import time
from urllib.parse import parse_qs, urlparse

from selenium import webdriver


def _league_id_from_url(url):
    ids = parse_qs(urlparse(url).query).get("leagueId")
    return ids[0] if ids else None


def _league_id_from_browser(driver):
    """Look through every open tab for an ESPN URL containing leagueId=..."""
    for handle in driver.window_handles:
        try:
            driver.switch_to.window(handle)
            league_id = _league_id_from_url(driver.current_url)
        except Exception:
            continue
        if league_id:
            return league_id
    return None


def get_espn_credentials(max_wait_time=300, poll_interval=2, league_page_wait=20):
    """
    Open ESPN in a browser, wait for the user to log in, and return
    {"swid", "espn_s2", "league_id_hint"}.

    The cookies are the proof of login: espn_s2 only exists once the user
    is authenticated into fantasy.

    league_id_hint is read from the browser URL (leagueId=...) as a fallback
    for league discovery. If the user isn't on a league page yet, we wait up
    to `league_page_wait` seconds for them to open one.
    """
    driver = webdriver.Chrome()
    try:
        driver.get("https://www.espn.com/fantasy/football/")

        print("Please log in to your ESPN account in the opened browser window.")
        print("Complete any two-factor authentication if prompted.")
        print("Once logged in, open your fantasy football league page.")

        start_time = time.time()
        creds = None
        while time.time() - start_time < max_wait_time:
            cookies = {c["name"]: c["value"] for c in driver.get_cookies()}
            swid = cookies.get("SWID")
            espn_s2 = cookies.get("espn_s2")

            if swid and espn_s2:
                creds = {"swid": swid, "espn_s2": espn_s2}
                break
            time.sleep(poll_interval)

        if creds is None:
            raise TimeoutError("Login timed out. Please try again.")

        print("Login detected. Credentials retrieved.")

        hint = _league_id_from_browser(driver)
        if not hint and league_page_wait:
            print(
                f"Tip: open your league's page now so we can detect it "
                f"(waiting up to {league_page_wait}s)..."
            )
            deadline = time.time() + league_page_wait
            while time.time() < deadline and not hint:
                time.sleep(1)
                hint = _league_id_from_browser(driver)

        creds["league_id_hint"] = hint
        return creds
    finally:
        driver.quit()
