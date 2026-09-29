import argparse

from fantasy_auth import delete_saved_credentials, get_league


def main():
    parser = argparse.ArgumentParser(description="Fantasy football helper")
    parser.add_argument(
        "--forget",
        action="store_true",
        help="Delete saved ESPN credentials and exit",
    )
    args = parser.parse_args()

    if args.forget:
        delete_saved_credentials()
        return

    league = get_league()
    print(f"\nConnected to: {league.settings.name} ({league.year})")

    for team in league.teams:
        print(f"  {team.team_name}: {team.wins}-{team.losses}")
    # ---- Prediction model goes here ----
    # e.g. free agents:  league.free_agents(size=50)
    #      rosters:      [team.roster for team in league.teams]


if __name__ == "__main__":
    main()
