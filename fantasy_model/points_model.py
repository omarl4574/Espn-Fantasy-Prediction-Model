"""XGBoost weekly-points model, a no-ML fallback, and rest-of-season (ROS) projection."""

import numpy as np
import pandas as pd

from .config import DEFAULT_PPG, EXTERNAL_WEIGHT, INJURY_FACTOR, POSITIONS
from .data import FEATURE_COLS, upcoming_features


def split_train_val(df, val_frac=0.2, min_val=100):
    """
    Time-ordered split, never random. Validate on the most recent games from the
    league's OWN ESPN data (true league scoring) when there are enough of them;
    otherwise on the most recent rows overall.
    """
    df = df.sort_values(["year", "week"]).reset_index(drop=True)
    source = df["source"] if "source" in df else pd.Series("espn", index=df.index)
    espn_idx = df.index[source == "espn"]
    n_val = int(len(espn_idx) * val_frac)
    if n_val >= min_val:
        val_idx = espn_idx[-n_val:]
    else:
        val_idx = df.index[int(len(df) * (1 - val_frac)) :]
    return df.drop(val_idx), df.loc[val_idx]


def _weights(d):
    if "source" not in d:
        return np.ones(len(d))
    return np.where(d["source"] == "external", EXTERNAL_WEIGHT, 1.0)


class PointsModel:
    def __init__(self):
        self.model = None

    def fit(self, df, val_frac=0.2, min_rows=300):
        import xgboost as xgb

        if len(df) == 0 or "target" not in df:
            raise RuntimeError("No training rows available.")
        df = df.dropna(subset=["target"])
        if len(df) < min_rows:
            raise RuntimeError(
                f"Only {len(df)} training rows; need at least {min_rows}. "
                "Enable external NFL data (nflreadpy) or load more past seasons."
            )

        train, val = split_train_val(df, val_frac)
        if "source" in df:
            print("  Rows by source:", df["source"].value_counts().to_dict())

        params = dict(
            learning_rate=0.03,
            max_depth=4,
            subsample=0.8,
            colsample_bytree=0.8,
            min_child_weight=5,
            objective="reg:squarederror",
            random_state=42,
        )
        probe = xgb.XGBRegressor(n_estimators=1000, early_stopping_rounds=30, **params)
        probe.fit(
            train[FEATURE_COLS],
            train["target"],
            sample_weight=_weights(train),
            eval_set=[(val[FEATURE_COLS], val["target"])],
            verbose=False,
        )

        preds = probe.predict(val[FEATURE_COLS])
        baseline = (
            val["avg_prior"]
            .fillna(val["prior_season_avg"])
            .fillna(train["target"].mean())
        )
        mae_model = (val["target"] - preds).abs().mean()
        mae_base = (val["target"] - baseline).abs().mean()
        print(
            f"  Validation MAE: model {mae_model:.2f} vs 'season average' baseline {mae_base:.2f}"
        )

        # Refit on everything with the best number of trees found above.
        self.model = xgb.XGBRegressor(n_estimators=probe.best_iteration + 1, **params)
        self.model.fit(df[FEATURE_COLS], df["target"], sample_weight=_weights(df))
        return self

    def predict(self, feature_df):
        return self.model.predict(feature_df[FEATURE_COLS])


class BaselinePointsModel:
    """
    No-ML fallback for when there isn't enough data to train: use ESPN's own
    projection, then recent form, then last season, then a positional default.
    """

    def predict(self, feature_df):
        f = feature_df
        est = f["espn_proj"]
        for col in ("last3", "avg_prior", "prior_season_avg"):
            est = est.fillna(f[col])
        default = sum(
            f[f"pos_{position}"] * DEFAULT_PPG[position] for position in POSITIONS
        )
        return est.fillna(default).to_numpy(dtype=float)


def games_remaining(player, current_week, last_week):
    weeks = range(current_week, last_week + 1)
    sched = getattr(player, "schedule", None) or {}
    if sched:
        played = set()
        for k in sched:
            try:
                played.add(int(k))
            except (TypeError, ValueError):
                pass
        if played:  # skips bye weeks when the schedule is available
            return sum(1 for w in weeks if w in played)
    return len(weeks)


def project_ros(model, league, players, prior):
    """{playerId: expected points from now to end of regular season}."""
    week = league.current_week
    last_week = league.settings.reg_season_count

    players = [player for player in players if player.position in POSITIONS]
    feats = pd.DataFrame(
        [upcoming_features(player, league, prior) for player in players]
    )
    per_game = model.predict(feats)

    ros = {}
    for player, ppg in zip(players, per_game):
        n = games_remaining(player, week, last_week)
        status = str(getattr(player, "injuryStatus", "ACTIVE")).upper()
        ros[player.playerId] = float(ppg) * n * INJURY_FACTOR.get(status, 1.0)
    return ros
