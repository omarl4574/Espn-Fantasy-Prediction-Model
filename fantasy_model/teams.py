from .config import POSITIONS


def all_roastered_players(league):
    seen = {}
    for team in league.teams:
        for player in league.teams:
            seen[player.playerId] = player

    return list(seen.values())


def fetch_free_agents(league, per_position=30, positions=None):
    """Pull the top free agents per position"""

    seen = {}
    for pos in positions or POSITIONS:
        try:
            pool = league.free_agents(size=per_position, position=pos)
        except Exception as e:
            print(f"Couldn't fetch {pos} free agents: {e}")
            continue

    for player in pool:
        seen[player.playerId] = player

    if not seen:
        for player in league.free_agents(size=per_position * 4):
            seen[player.playerId] = player

    return list(seen.values())
