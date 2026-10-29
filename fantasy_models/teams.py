from .config import POSITIONS


def all_rostered_players(league):
    seen = {}
    for team in league.teams:
        for player in team.roster:
            seen[player.playerId] = player
    return list(seen.values())


def fetch_free_agents(league, per_position=30, positions=None):
    """Pull the top free agents at each position so every position is covered."""
    seen = {}
    for pos in positions or POSITIONS:
        try:
            pool = league.free_agents(size=per_position, position=pos)
        except Exception as e:
            print(f"  Couldn't fetch {pos} free agents: {e}")
            continue
        for player in pool:
            seen[player.playerId] = player
    if not seen:  # fallback: unfiltered pool
        for player in league.free_agents(size=per_position * 4):
            seen[player.playerId] = player
    return list(seen.values())


def find_my_team(league, swid):
    """Match the logged-in SWID to a team's owner id; fall back to asking."""
    swid_l = swid.lower()
    for team in league.teams:
        for owner in getattr(team, "owners", None) or []:
            oid = owner.get("id") if isinstance(owner, dict) else None
            if oid and oid.lower() == swid_l:
                return team

    print("Couldn't auto-detect your team. Which one is yours?")
    for i, team in enumerate(league.teams, 1):
        print(f"  {i}. {team.team_name}")
    while True:
        choice = input("Team number: ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(league.teams):
            return league.teams[int(choice) - 1]
