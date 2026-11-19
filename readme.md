# ESPN Fantasy Football Assistant

A Python tool that connects to your ESPN fantasy football league and uses your league's real data to help you make better decisions:

- **Who should I pick up or drop?** Finds free agents who would actually improve your starting lineup, and which player to drop for them.
- **Which trades are fair, or slightly in my favor?** Searches every other team in your league for trades that help you without being a rip-off for them.
- **Who is actually worth rostering?** Ranks your players by projected rest-of-season points and Value Over Replacement Player (VORP).

It works for any ESPN league: your league ID and lineup requirements (superflex, WR/TE flex, no kicker, etc.) are detected automatically, so nothing is hardcoded to one league.

It runs either as a **one-page website** (`python app.py`) or as a command-line program (`python main.py`). Both use the same analysis code.

> **Status:** early development. ESPN does not publish an official API, so some endpoints used here are undocumented and may change. This project is not affiliated with ESPN.

---

## How it works

1. **Log in once.** A Chrome window opens to ESPN. You log in normally (2FA works). The program reads the two cookies the `espn_api` library needs (`SWID` and `espn_s2`) and closes the browser. Your password is never seen or stored.
2. **Optionally save the cookies locally** so you don't have to log in next time. If they expire, the program detects it, logs in again, and re-saves them.
3. **Find your league automatically** from your account (or from the league page you open in the browser).
4. **Read your league's lineup settings** (QB/RB/WR/TE/FLEX/OP/K/DST counts) so every calculation matches your league.
5. **Train a model** to predict how many points each player will score, then project rest-of-season (ROS) totals.
6. **Print recommendations:** roster VORP table, drop/add suggestions, and trade ideas.

### The three models

| Model | What it does | File |
|---|---|---|
| **XGBoost** | Predicts a player's points for their next game from rolling averages, variance, ESPN's own projection, last season's average, and position. ROS = prediction x games remaining x an injury factor. | `fantasy_models/points_model.py` |
| **VORP** | Compares each player to the average of the best free agents at their position ("replacement level"). Drop/add suggestions use the change in your *best possible lineup*, so dropping a bench player correctly costs almost nothing. | `fantasy_models/vorp.py` |
| **Knapsack-style trade search** | Maximizes **your** lineup gain, subject to constraints that keep the trade believable: the other team's lineup can't lose more than a tolerance, the value they receive vs. give must be roughly even, and roster sizes stay close. Solved exactly by enumeration (trades are tiny). | `fantasy_models/trades.py` |

All three share one number per player, projected ROS points, and one lineup evaluator (`lineup.py`) that solves "what's the best starting lineup from these players?" as an assignment problem for any league layout.

### Where the training data comes from

- **Your league's ESPN history** (current season plus up to 3 earlier seasons), scored with your league's real scoring.
- **nflverse** (free public NFL stats via `nflreadpy`) for earlier seasons your league history doesn't have, so the model has enough data even if you've only played a season or two. Points are recomputed with your league's points-per-reception. These rows are down-weighted and never used for validation.
- If there still isn't enough data, the program falls back to ESPN's own projections instead of crashing.

---

## Setup

### Requirements

- Python 3.9 or newer
- Google Chrome installed (used for the login window; Selenium downloads the matching driver automatically)
- An ESPN account that belongs to a fantasy football league

### Install

```bash
# 1. Get the project and enter the folder
cd fantasy_project

# 2. Create and activate a virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate          # macOS / Linux
.venv\Scripts\activate             # Windows

# 3. Install dependencies
pip install -r requirements.txt
```

### Run

```bash
python main.py               # normal run
python main.py --inspect     # print raw ESPN fields to check everything is wired correctly
python main.py --no-external # skip downloading extra NFL stats
python main.py --forget      # delete saved credentials and exit
```

On the first run (command line or website):

1. A Chrome window opens. Log in to ESPN, then open your fantasy football league page.
2. When asked, choose whether to save your credentials locally.
3. Wait for the models to train (a minute or two the first time). Results print in the terminal.

### Website

```bash
python app.py                 # opens http://127.0.0.1:5000
python app.py --port 8080     # use another port
python app.py --no-browser    # don't open a browser tab automatically
```

Login and team selection happen in the terminal first (a Chrome window opens for the ESPN login). Then the site starts and the analysis runs in the background with a progress bar. The page is a single screen:

- **Top, center:** your roster, with each player's starting slot (or bench), projected rest-of-season points, and VORP
- **Bottom left:** drop/add recommendations
- **Bottom right:** possible trades
- **Settings** button: edit the trade, drop/add, and model settings in a dialog. Saving does not change the results by itself.
- **Reload** button: re-downloads your league from ESPN, retrains the model, and applies the saved settings. It lights up when your saved settings differ from the ones the current results were computed with.

The server only listens on `127.0.0.1` (this computer) by default, and your ESPN cookies never leave the server. Don't expose it to a network without adding authentication.

### Where credentials are stored

If you choose to save them, the cookies go in `~/.espn_fantasy/credentials.json` (readable only by your user), outside the project folder so they can't be committed to git by accident. **Treat that file like a password:** anyone with those cookies can act as you on ESPN. Use `python main.py --forget` to delete it.

---

## Configuration

The settings below can be edited in the website's **Settings** dialog (saved to `~/.espn_fantasy/settings.json`, which the command-line version also reads). Their defaults live in `fantasy_models/config.py`. All thresholds are in **total rest-of-season fantasy points**.

| Setting | Meaning |
|---|---|
| `MIN_PICKUP_GAIN` | Only suggest a drop/add that improves your lineup by at least this much |
| `MAX_TRADE_SIZE` | Max players per side in a trade (3 makes the search much slower) |
| `MIN_MY_GAIN` | A trade must improve your lineup by at least this |
| `THEIR_TOLERANCE` | ...while costing the other team no more than this |
| `MIN_VALUE_RATIO` | Value they receive / value they give must be at least this |
| `N_EXTERNAL_SEASONS` | How many past seasons of NFL stats to download |
| `EXTERNAL_WEIGHT` | How much external rows count compared to your league's own data |
| `INJURY_FACTOR` | Multiplier on projected points by injury status |

If you get no trade ideas, loosen `MIN_MY_GAIN`/`THEIR_TOLERANCE`. If you get too many, tighten them.

---

## Project structure

```
fantasy_project/
├── app.py                       # website entry point (python app.py)
├── main.py                      # command-line entry point
├── requirements.txt
├── README.md
├── .gitignore
│
├── fantasy_auth/                # getting into ESPN
│   ├── __init__.py
│   ├── browser_login.py         # Selenium login; reads SWID + espn_s2 cookies
│   ├── storage.py               # optional local credential saving
│   ├── leagues.py               # finds your leagues automatically
│   └── session.py               # saved creds -> validate -> re-login on expiry
│
├── fantasy_models/              # the analysis
│   ├── pipeline.py              # runs everything, RETURNS data (used by CLI and website)
│   ├── settings.py              # editable settings: validation + saving
│   ├── config.py                # default values
│   ├── slots.py                 # detects your league's lineup + scoring settings
│   ├── teams.py                 # rosters, free agents, finds your team
│   ├── data.py                  # ESPN data -> leak-free training table
│   ├── external_data.py         # extra training data from nflverse
│   ├── points_model.py          # XGBoost + no-ML fallback + ROS projection
│   ├── lineup.py                # best lineup (and who starts) for any league layout
│   ├── vorp.py                  # VORP + drop/add recommendations
│   └── trades.py                # knapsack-style trade search
│
└── fantasy_web/                 # the website
    ├── __init__.py              # Flask app factory
    ├── routes.py                # page + JSON endpoints
    ├── state.py                 # runs the analysis in a background thread
    ├── templates/index.html     # the one-page layout
    └── static/
        ├── style.css
        └── app.js               # renders the panels, settings dialog, reload button
```

How the website works: `index.html` loads `app.js`, which polls `/api/status` while the analysis runs in a background thread, then fetches `/api/data` (the same dict `pipeline.run_analysis` returns) and draws the three panels. Settings go through `/api/settings`, and **Reload** calls `/api/reload`.

---

## Troubleshooting

| Problem | What to try |
|---|---|
| Login never completes | Make sure you log in and open a fantasy page; the program waits for both cookies (`SWID` and `espn_s2`). |
| "No leagues found" | The program prints a summary of ESPN's response. Open your league page right after logging in so the league ID can be read from the URL. |
| "Only N training rows" | Install `nflreadpy` and `pyarrow` (they're in `requirements.txt`) and run without `--no-external`. The program also falls back to ESPN projections automatically. |
| "ESPN rejected the credentials" | The cookies expired or were copied wrong. Run `python main.py --forget` and log in again. |
| Recommendations look off | Run `python main.py --inspect` and check that the detected lineup slots match your league. |

---

## Known limitations

- **ESPN endpoints are undocumented** (league discovery, lineup settings, scoring settings) and could change without notice.
- **IDP leagues** (individual defensive players like LB/CB) are not supported yet; those slots are treated as empty.
- **Kickers and defenses** are not in the external NFL data, so their predictions are simpler.
- **Scoring from external data is approximate** for leagues with custom bonuses.
- **Trade ideas are starting points.** Your opponents don't evaluate trades the way this program does.
- A trade where you receive more players than you give may force a drop, which isn't modeled yet.
- Bye weeks are skipped only if ESPN's schedule data is available; playoff weeks aren't projected.

---

## TODO

### Done
- [x] Refactor the analysis so it returns data instead of printing (`pipeline.py`)
- [x] One-page Flask site: roster, drop/add, and trades panels
- [x] Settings dialog with validation, saved between runs
- [x] Reload button that retrains and applies new settings, with a progress bar
- [x] Analysis runs in a background thread; past seasons and downloaded NFL stats are cached in memory between reloads

### Website
- [ ] Log in from the website (a "Connect" page) instead of the terminal at startup
- [ ] Skip retraining when only trade/drop-add settings changed (they only need recomputing, not a new model)
- [ ] Save the trained model and last results to disk so the page shows something instantly on startup
- [ ] Show trade-search progress and allow cancelling (3-for-3 searches are slow)
- [ ] Sortable/filterable tables, player detail view, and charts
- [ ] Run under a real server (waitress/gunicorn) instead of Flask's development server

### Hosting for other people (the hard part)
- [ ] The Selenium login only works when the app runs **on the user's own computer**. For a hosted site, replace it (e.g. user pastes `SWID` + `espn_s2`, a browser extension, or a bookmarklet)
- [ ] Store each user's credentials **encrypted** (not a plain JSON file), tied to a user session; never log them
- [ ] Add user accounts, per-user state (the app currently holds one league in memory), and a "disconnect and delete my data" button
- [ ] Add authentication and CSRF protection before exposing it beyond `127.0.0.1`
- [ ] Rate limiting / caching for ESPN requests

### Modeling improvements
- [ ] Support IDP leagues
- [ ] Better K and D/ST predictions
- [ ] Model bye weeks and playoff weeks properly
- [ ] Handle roster-size limits (forced drops) in trade search
- [ ] Waiver priority / FAAB budget awareness
- [ ] Hyperparameter tuning and feature importance reporting
- [ ] Estimate how likely each opponent is to accept a trade

### Project quality
- [ ] Add automated tests (`pytest`) for lineup, VORP, trades, feature building, and the Flask routes
- [ ] Replace `print` with the `logging` module
- [ ] Add type hints and docstrings throughout
- [ ] Choose and add a license
- [ ] Add screenshots to this README
