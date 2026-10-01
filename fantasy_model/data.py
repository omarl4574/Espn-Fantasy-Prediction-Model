"""Turn espn_api players into a leak-free (player, week) training table."""

import numpy as np
import pandas as pd
from espn_api.football import League

from .config import POSITIONS
from .teams import all_rostered_players


def weekly_stats(player):
    """{week: (actual_points, projected_points)}, excluding week 0 (season total)."""
    out = {}
    for wk, s in (getattr(player, "stats", None) or {}).items():
        try:
            wk = int(wk)
        except (TypeError, ValueError):
            continue
        if wk == 0 or not isinstance(s, dict):
            continue
        out[wk] = (s.get("points"), s.get("projected_points"))
    return out


def make_features(history, week, position, proj, prior_avg):
    """
    Features for predicting `week`, using ONLY games before it.
    history = actual points from earlier weeks, in order.
    """
    h = np.asarray(history, dtype=float)
    n = len(h)
    feats = {
        "week": week,
        "games_prior": n,
        "avg_prior": h.mean() if n else np.nan,
        "last1": h[-1] if n else np.nan,
        "last3": h[-3:].mean() if n else np.nan,
        "last5": h[-5:].mean() if n else np.nan,
        "std_prior": h.std() if n > 1 else np.nan,
        "max_prior": h.max() if n else np.nan,
        "espn_proj": proj if proj is not None else np.nan,
        "prior_season_avg": prior_avg if prior_avg is not None else np.nan,
    }
    for pos in POSITIONS:
        feats[f"pos_{pos}"] = int(position == pos)
    return feats


FEATURE_COLS = list(make_features([], 1, "QB", None, None).keys())


def load_league_history(league, creds, n_prior=3):
    """{year: League} for the current season plus up to n_prior earlier ones."""
    leagues = {league.year: league}
    for y in range(league.year - n_prior, league.year):
        try:
            leagues[y] = League(
                league_id=league.league_id,
                year=y,
                espn_s2=creds["espn_s2"],
                swid=creds["swid"],
            )
            print(f"  Loaded {y} season.")
        except Exception as e:
            print(f"  Skipping {y}: {e}")
    return leagues


def _last_completed_week(league, is_current):
    return league.current_week - 1 if is_current else league.current_week


def season_averages(leagues):
    """{(year, playerId): average weekly points that season}."""
    current_year = max(leagues)
    avgs = {}
    for year, lg in leagues.items():
        last_wk = _last_completed_week(lg, year == current_year)
        for player in all_rostered_players(lg):
            pts = [
                a
                for wk, (a, _) in weekly_stats(player).items()
                if a is not None and wk <= last_wk
            ]
            if pts:
                avgs[(year, player.playerId)] = float(np.mean(pts))
    return avgs


def build_training_frame(leagues, prior):
    current_year = max(leagues)
    rows = []
    for year, lg in leagues.items():
        last_wk = _last_completed_week(lg, year == current_year)
        for player in all_rostered_players(lg):
            if player.position not in POSITIONS:
                continue
            stats = weekly_stats(player)
            history = []
            for wk in sorted(stats):
                if wk > last_wk:
                    break
                actual, proj = stats[wk]
                if actual is None:
                    continue
                row = make_features(
                    history,
                    wk,
                    player.position,
                    proj,
                    prior.get((year - 1, player.playerId)),
                )
                row.update(
                    target=actual, year=year, playerId=player.playerId, source="espn"
                )
                rows.append(row)
                history.append(actual)
    return pd.DataFrame(rows)


def upcoming_features(player, league, prior):
    """Feature row for the player's next game in the CURRENT league."""
    week = league.current_week
    stats = weekly_stats(player)
    history = [
        stats[w][0] for w in sorted(stats) if w < week and stats[w][0] is not None
    ]
    proj = stats.get(week, (None, None))[1]
    return make_features(
        history,
        week,
        player.position,
        proj,
        prior.get((league.year - 1, player.playerId)),
    )
