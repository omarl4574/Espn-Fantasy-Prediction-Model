"""Tunable settings. Lineup slots are auto-detected per league; thresholds live here."""

POSITIONS = ["QB", "RB", "WR", "TE", "K", "D/ST"]

# FALLBACK ONLY: used if the league's real lineup settings can't be fetched.
# Normally the slots are read from the user's league automatically (see slots.py).
DEFAULT_LINEUP_SLOTS = {
    "QB": 1,
    "RB": 2,
    "WR": 2,
    "TE": 1,
    "RB/WR/TE": 1,
    "D/ST": 1,
    "K": 1,
}

# Multiplier on rest-of-season value by ESPN injury status.
INJURY_FACTOR = {
    "ACTIVE": 1.0,
    "QUESTIONABLE": 0.95,
    "DOUBTFUL": 0.5,
    "OUT": 0.0,
    "INJURY_RESERVE": 0.0,
}

# All thresholds below are in total rest-of-season (ROS) fantasy points.
MIN_PICKUP_GAIN = 5.0  # only suggest a drop/add that improves your lineup by this much

MAX_TRADE_SIZE = 2  # max players per side (3 makes the search much slower)
MIN_MY_GAIN = 8.0  # trade must improve MY lineup by at least this
THEIR_TOLERANCE = 6.0  # ...while costing THEM no more than this (keeps it "fair-ish")
MIN_VALUE_RATIO = 0.90  # value they receive / value they give must be >= this

# ---- Extra training data from nflverse (free public NFL stats) ----
N_EXTERNAL_SEASONS = (
    5  # how many past seasons to pull (only ones your league history lacks)
)
EXTERNAL_WEIGHT = 0.5  # external rows count half as much as rows scored by YOUR league
# Keep only fantasy-relevant players (ESPN rows are rostered players, so match that).
# Judged from points BEFORE the game, so there's no leakage.
EXTERNAL_MIN_AVG = {"QB": 8.0, "RB": 4.0, "WR": 4.0, "TE": 3.0}

# Used by the no-ML fallback when a player has no projection or history.
DEFAULT_PPG = {"QB": 15.0, "RB": 8.0, "WR": 8.0, "TE": 6.0, "K": 7.0, "D/ST": 7.0}
