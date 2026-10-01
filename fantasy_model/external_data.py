"""
Extra training data from nflverse (free, public weekly NFL stats via nflreadpy).

ESPN only exposes seasons your league existed, and only for rostered
players. nflverse has years of weekly stats, so the model can train on far
more games. We recompute fantasy points with YOUR league's points-per-reception
so the scale matches. Covers QB/RB/WR/TE only (K and D/ST aren't in this data).
"""

import numpy as np
import pandas as pd

from .config import EXTERNAL_MIN_AVG, N_EXTERNAL_SEASONS
from .data import make_features
from .slots import fetch_reception_points

SKILL_POSITIONS = list(EXTERNAL_MIN_AVG)


def _to_pandas(frame):
    return frame.to_pandas() if hasattr(frame, "to_pandas") else frame


def load_external_weekly(seasons):
    import nflreadpy as nfl  # imported lazily so the rest of the app works without it

    return _to_pandas(nfl.load_player_stats(seasons=list(seasons)))


def load_espn_to_gsis():
    """{espn_id: gsis_id} so ESPN players can be matched to nflverse players."""
    try:
        import nflreadpy as nfl

        ids = _to_pandas(nfl.load_ff_playerids()).dropna(subset=["espn_id", "gsis_id"])
        return {int(e): g for e, g in zip(ids["espn_id"], ids["gsis_id"])}
    except Exception as e:
        print(
            f"  Couldn't load ESPN<->NFL player id map ({e}); skipping prior-season fill."
        )
        return {}


def prepare_weekly(weekly, rec_points):
    """Regular-season skill-position rows with a `points` column in league scoring."""
    df = weekly.copy()
    if "fantasy_points" in df.columns and "receptions" in df.columns:
        df["points"] = df["fantasy_points"].fillna(0) + rec_points * df[
            "receptions"
        ].fillna(0)
    elif "fantasy_points_ppr" in df.columns:
        print("  Using PPR points as an approximation (standard columns missing).")
        df["points"] = df["fantasy_points_ppr"]
    else:
        raise KeyError(
            "nflverse data has no fantasy_points columns; its schema may have changed"
        )
    if "season_type" in df.columns:
        df = df[df["season_type"] == "REG"]
    df = df[df["position"].isin(SKILL_POSITIONS)]
    return df.sort_values(["player_id", "season", "week"])


def season_avg_map(prepared):
    """{(gsis_id, season): average weekly points}."""
    avg = prepared.groupby(["player_id", "season"])["points"].mean()
    return {(pid, int(season)): float(v) for (pid, season), v in avg.items()}


def build_external_rows(prepared, target_seasons):
    """Leak-free (player, week) rows, same features as the ESPN training table."""
    avgs = season_avg_map(prepared)
    target = set(int(s) for s in target_seasons)
    rows = []
    for (pid, season), g in prepared.groupby(["player_id", "season"]):
        season = int(season)
        if season not in target:
            continue
        pos = g["position"].iloc[0]
        prior = avgs.get((pid, season - 1))
        history = []
        for wk, pts in zip(g["week"], g["points"]):
            row = make_features(history, int(wk), pos, None, prior)
            # Relevance filter uses only information available BEFORE this game.
            ref = row["avg_prior"] if history else prior
            if ref is not None and not np.isnan(ref) and ref >= EXTERNAL_MIN_AVG[pos]:
                row.update(
                    target=float(pts), year=season, playerId=pid, source="external"
                )
                rows.append(row)
            history.append(float(pts))
    return pd.DataFrame(rows)


def external_training_rows(league, creds, espn_years, n_external=N_EXTERNAL_SEASONS):
    """
    Returns (rows_df, season_avgs). Only seasons your ESPN history lacks are
    added, so no player-week is counted twice.
    """
    wanted = [
        y for y in range(league.year - n_external, league.year) if y not in espn_years
    ]

    rec = fetch_reception_points(league.league_id, league.year, creds)
    if rec is None:
        print("  Couldn't read league scoring; assuming 0.5 points per reception.")
        rec = 0.5

    first = (
        min(wanted + [league.year - 1]) - 1
    )  # one extra season for prior-season averages
    print(
        f"  Downloading NFL weekly stats {first}-{league.year - 1} (reception pts = {rec})..."
    )
    prepared = prepare_weekly(load_external_weekly(range(first, league.year)), rec)
    return build_external_rows(prepared, wanted), season_avg_map(prepared)


def fill_prior_from_external(prior, players, year, espn_to_gsis, ext_avgs):
    """Fill missing last-season averages for current players using nflverse data."""
    filled = 0
    for player in players:
        key = (year - 1, player.playerId)
        if key in prior:
            continue
        try:
            gsis = espn_to_gsis.get(int(player.playerId))
        except (TypeError, ValueError):
            continue
        val = ext_avgs.get((gsis, year - 1))
        if val is not None:
            prior[key] = val
            filled += 1
    return filled
