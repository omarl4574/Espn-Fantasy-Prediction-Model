import argparse

import pandas as pd

from fantasy_auth import delete_saved_credentials, get_session
from fantasy_model.data import (
    build_training_frame,
    load_league_history,
    season_averages,
)
from fantasy_model.external_data import (
    external_training_rows,
    fill_prior_from_external,
    load_espn_to_gsis,
)
from fantasy_model.lineup import LineupEvaluator
from fantasy_model.points_model import BaselinePointsModel, PointsModel, project_ros
from fantasy_model.slots import get_lineup_slots, positions_in_use
from fantasy_model.teams import all_rostered_players, fetch_free_agents, find_my_team
from fantasy_model.trades import find_trades
from fantasy_model.vorp import best_drop_add, replacement_levels, vorp_table


def inspect_league(league, creds):
    """Sanity-check that espn_api is exposing the fields the models rely on."""
    team = league.teams[0]
    player = team.roster[0]
    print("current_week:", league.current_week)
    print("reg_season_count:", league.settings.reg_season_count)
    print("team owners field:", getattr(team, "owners", "MISSING"))
    print(
        "player:",
        player.name,
        player.position,
        player.playerId,
        getattr(player, "injuryStatus", None),
    )
    print("stats keys:", sorted(player.stats.keys())[:20])
    wk = next((k for k in sorted(player.stats) if k != 0), None)
    print(f"stats[{wk}]:", player.stats.get(wk))
    print("schedule sample:", list((getattr(player, "schedule", {}) or {}).items())[:3])
    print("eligibleSlots sample:", getattr(player, "eligibleSlots", "MISSING"))
    get_lineup_slots(league, creds)


def main():
    parser = argparse.ArgumentParser(description="Fantasy football helper")
    parser.add_argument(
        "--forget", action="store_true", help="Delete saved credentials and exit"
    )
    parser.add_argument(
        "--no-external", action="store_true", help="Skip downloading extra NFL stats"
    )
    parser.add_argument(
        "--inspect", action="store_true", help="Print raw espn_api fields and exit"
    )
    args = parser.parse_args()

    if args.forget:
        delete_saved_credentials()
        return

    league, creds = get_session()
    print(
        f"\nConnected to: {league.settings.name} ({league.year}), week {league.current_week}"
    )

    if args.inspect:
        inspect_league(league, creds)
        return

    my_team = find_my_team(league, creds["swid"])
    print(f"Your team: {my_team.team_name}")
    slots = get_lineup_slots(league, creds)
    positions = positions_in_use(slots)

    print("Loading past seasons for training...")
    history = load_league_history(league, creds)
    prior = season_averages(history)

    print("Training points model...")
    train_df = build_training_frame(history, prior)
    if len(train_df):
        print(
            "  Rows from your league's ESPN history, by season:",
            train_df.groupby("year").size().to_dict(),
        )
    else:
        print("  No usable rows from your league's ESPN history.")

    ext_avgs = {}
    if not args.no_external:
        try:
            ext_rows, ext_avgs = external_training_rows(league, creds, set(history))
            if len(ext_rows):
                train_df = pd.concat([train_df, ext_rows], ignore_index=True)
                print(f"  Added {len(ext_rows)} rows from NFL stats (nflverse).")
        except ImportError:
            print(
                "  nflreadpy not installed, skipping extra data (pip install nflreadpy pyarrow)."
            )
        except Exception as e:
            print(f"  Couldn't load extra NFL data: {e}")

    print(f"  {len(train_df)} player-week rows total")
    try:
        model = PointsModel().fit(train_df)
    except RuntimeError as e:
        print(
            f"  {e}\n  Falling back to ESPN-projection baseline (no ML) until there's more data."
        )
        model = BaselinePointsModel()

    print("Fetching free agents and projecting rest of season...")
    free_agents = fetch_free_agents(league, positions=positions)
    players = all_rostered_players(league) + free_agents
    if ext_avgs:
        n = fill_prior_from_external(
            prior, players, league.year, load_espn_to_gsis(), ext_avgs
        )
        print(f"  Filled last-season averages for {n} players from NFL stats.")
    ros = project_ros(model, league, players, prior)
    repl = replacement_levels(free_agents, ros)
    evaluator = LineupEvaluator(slots, ros)

    print("\n=== Your roster by VORP (rest-of-season) ===")
    for player, pts, v in vorp_table(my_team.roster, ros, repl):
        print(
            f"  {player.name:<25} {player.position:<5} ROS {pts:6.1f}   VORP {v:+6.1f}"
        )

    print("\n=== Drop/add suggestions ===")
    moves = best_drop_add(my_team, free_agents, evaluator)
    if not moves:
        print("  No pickup improves your lineup enough. Hold steady.")
    for fa, drop, gain in moves:
        print(
            f"  Add {fa.name} ({fa.position}), drop {drop.name}: +{gain:.1f} lineup pts"
        )

    print("\n=== Trade ideas (fair or slightly in your favor) ===")
    others = [t for t in league.teams if t.team_id != my_team.team_id]
    trades = find_trades(my_team, others, ros, evaluator)
    if not trades:
        print(
            "  No trades met the fairness constraints. Loosen thresholds in config.py."
        )
    for t in trades:
        print(
            f"  With {t['team']}: give {', '.join(t['give'])} for {', '.join(t['get'])}\n"
            f"     you {t['my_gain']:+.1f}, them {t['their_gain']:+.1f}, "
            f"value ratio {t['value_ratio']:.2f}"
        )


if __name__ == "__main__":
    main()
