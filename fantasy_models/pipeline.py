"""
The whole analysis as one function that RETURNS plain, JSON-friendly data.
Both the command line (main.py) and the website (fantasy_web) call it.
"""
from datetime import datetime, timezone

import pandas as pd
from espn_api.football import League

from .data import build_training_frame, load_league_history, season_averages
from .external_data import external_training_rows, fill_prior_from_external, load_espn_to_gsis
from .lineup import LineupEvaluator
from .points_model import BaselinePointsModel, PointsModel, project_ros
from .slots import get_lineup_slots, positions_in_use
from .teams import all_rostered_players, fetch_free_agents
from .trades import find_trades
from .vorp import best_drop_add, replacement_levels, vorp_table


def _refresh_league(league, creds):
    """Re-download the league so rosters/free agents are current."""
    try:
        return League(
            league_id=league.league_id,
            year=league.year,
            espn_s2=creds["espn_s2"],
            swid=creds["swid"],
        )
    except Exception as e:
        print(f"  Couldn't refresh league data ({e}); using the previous snapshot.")
        return league


def _player_info(player, ros, repl, slot):
    status = str(getattr(player, "injuryStatus", "") or "")
    if status.upper() in ("ACTIVE", "NONE"):
        status = ""
    value = ros.get(player.playerId, 0.0)
    return {
        "id": player.playerId,
        "name": player.name,
        "position": player.position,
        "team": getattr(player, "proTeam", "") or "",
        "injury": status.replace("_", " ").title(),
        "ros": round(value, 1),
        "vorp": round(value - repl.get(player.position, 0.0), 1),
        "slot": slot,
    }


def run_analysis(league, creds, settings, my_team_id, progress=None, cache=None, refresh=False):
    """
    Returns (result_dict, league). `cache` lets repeat runs skip slow steps that
    don't change (past seasons, downloaded NFL stats). `progress(message, percent)`
    is called as each stage begins.
    """
    progress = progress or (lambda message, percent: None)
    cache = cache if cache is not None else {}

    if refresh:
        progress("Refreshing league data from ESPN...", 5)
        league = _refresh_league(league, creds)
    my_team = next(team for team in league.teams if team.team_id == my_team_id)

    progress("Reading your league's lineup settings...", 12)
    slots = get_lineup_slots(league, creds)
    positions = positions_in_use(slots)

    progress("Loading past seasons...", 20)
    if "past" not in cache:
        full = load_league_history(league, creds)
        cache["past"] = {year: lg for year, lg in full.items() if year != league.year}
    history = {league.year: league, **cache["past"]}
    prior = season_averages(history)

    progress("Building training data...", 30)
    train_df = build_training_frame(history, prior)
    espn_rows = len(train_df)

    ext_count, ext_avgs = 0, {}
    n_external = settings["n_external_seasons"]
    if n_external > 0:
        key = ("external", league.year, n_external)
        try:
            if key not in cache:
                progress("Downloading NFL stats (nflverse)...", 38)
                cache[key] = external_training_rows(
                    league, creds, set(history), n_external=n_external
                )
            ext_rows, ext_avgs = cache[key]
            if len(ext_rows):
                train_df = pd.concat([train_df, ext_rows], ignore_index=True)
                ext_count = len(ext_rows)
        except ImportError:
            print("  nflreadpy not installed, skipping extra data (pip install nflreadpy pyarrow).")
        except Exception as e:
            print(f"  Couldn't load extra NFL data: {e}")

    progress("Training the points model...", 50)
    try:
        model = PointsModel(external_weight=settings["external_weight"]).fit(train_df)
        model_type = "xgboost"
    except RuntimeError as e:
        print(f"  {e}\n  Falling back to ESPN-projection baseline (no ML) until there's more data.")
        model = BaselinePointsModel()
        model_type = "baseline"

    progress("Fetching free agents and projecting rest of season...", 70)
    free_agents = fetch_free_agents(league, positions=positions)
    players = all_rostered_players(league) + free_agents
    if ext_avgs:
        if "gsis" not in cache:
            cache["gsis"] = load_espn_to_gsis()
        fill_prior_from_external(prior, players, league.year, cache["gsis"], ext_avgs)
    ros = project_ros(model, league, players, prior)
    repl = replacement_levels(free_agents, ros)
    evaluator = LineupEvaluator(slots, ros)

    progress("Ranking your roster...", 80)
    slot_by_id = {player.playerId: slot for player, slot in evaluator.starters(my_team.roster)}
    roster = [
        _player_info(player, ros, repl, slot_by_id.get(player.playerId, "BENCH"))
        for player, _, _ in vorp_table(my_team.roster, ros, repl)
    ]
    roster.sort(key=lambda row: (row["slot"] == "BENCH", -row["ros"]))

    progress("Finding drop/add moves...", 88)
    drop_add = [
        {
            "add": _player_info(add, ros, repl, "FA"),
            "drop": _player_info(drop, ros, repl, "BENCH"),
            "gain": round(gain, 1),
        }
        for add, drop, gain in best_drop_add(
            my_team, free_agents, evaluator,
            min_gain=settings["min_pickup_gain"], top_n=settings["dropadd_results"],
        )
    ]

    progress("Searching for trades...", 92)
    others = [team for team in league.teams if team.team_id != my_team_id]
    trades = [
        {
            "team": trade["team"],
            "give": [_player_info(pl, ros, repl, "BENCH") for pl in trade["give_players"]],
            "get": [_player_info(pl, ros, repl, "BENCH") for pl in trade["get_players"]],
            "my_gain": round(trade["my_gain"], 1),
            "their_gain": round(trade["their_gain"], 1),
            "value_ratio": None if trade["value_ratio"] == float("inf")
            else round(trade["value_ratio"], 2),
        }
        for trade in find_trades(
            my_team, others, ros, evaluator,
            max_size=settings["max_trade_size"],
            min_my_gain=settings["min_my_gain"],
            their_tolerance=settings["their_tolerance"],
            min_value_ratio=settings["min_value_ratio"],
            top_n=settings["trade_results"],
        )
    ]

    progress("Done.", 100)
    result = {
        "league_name": league.settings.name,
        "season": league.year,
        "week": league.current_week,
        "team_name": my_team.team_name,
        "slots": slots,
        "model": {
            "type": model_type,
            "espn_rows": espn_rows,
            "external_rows": ext_count,
            **getattr(model, "metrics", {}),
        },
        "roster": roster,
        "drop_add": drop_add,
        "trades": trades,
        "settings": dict(settings),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    return result, league
