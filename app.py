"""
Start the website:  python app.py

Login and league/team selection happen in this terminal first (you may be asked
a couple of questions and a Chrome window will open). Then the site starts at
http://127.0.0.1:5000 and the analysis runs in the background.
"""
import argparse
import threading
import webbrowser

from fantasy_auth import get_session
from fantasy_models.settings import load_settings
from fantasy_models.teams import find_my_team
from fantasy_web import create_app


def main():
    parser = argparse.ArgumentParser(description="Fantasy football assistant (website)")
    parser.add_argument("--host", default="127.0.0.1",
                        help="Keep 127.0.0.1 so only this computer can open the site")
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--no-browser", action="store_true", help="Don't open a browser tab")
    args = parser.parse_args()

    league, creds = get_session()
    my_team = find_my_team(league, creds["swid"])
    print(f"Team: {my_team.team_name}")

    app = create_app(league, creds, my_team.team_id)
    app.config["STATE"].start(load_settings(), refresh=False)   # data was just loaded

    url = f"http://{args.host}:{args.port}"
    print(f"\nOpen {url}  (Ctrl+C to stop)\n")
    if not args.no_browser:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()

    # use_reloader=False: Flask's auto-reloader would re-run the login at startup.
    app.run(host=args.host, port=args.port, debug=False, use_reloader=False, threaded=True)


if __name__ == "__main__":
    main()
