"""
Trade search, framed as a small constrained knapsack:

  choose which of my players to give (G) and which of theirs to get (R)
  maximize my lineup gain
  subject to their lineup gain >= -THEIR_TOLERANCE (to not make it a rip-off for them)

    value they recieve / value they give >= MIN_VALUE_RATIO (to make it look fair on paper)
    my_lineup gain >= MIN_MY_GAIN
    |len(G) - len(R)| <= 1 (so roaster spots stay managable)

For Future Refrence:
  Trade sets are tiny, so we solve it exactly by enumeration. For bigger searches, swap in 
  an ILP solver (OR-Tools / PuLP) with the same constraints
"""

from itertools import combinations
from .config import MAX_TRADE_SIZE, MIN_MY_GAIN, MIN_VALUE_RATIO, THEIR_TOLERANCE


def find_trades(
    my_team,
    other_teams,
    ros,
    evaluator,
    max_size=MAX_TRADE_SIZE,
    min_my_gain=MIN_MY_GAIN,
    min_value_ratio=MIN_VALUE_RATIO,
    their_tolerance=THEIR_TOLERANCE,
    top_n=10
):
    """
    Find trades that improve my team and are acceptable to the other team.
    Returns a list of tuples: (my_players, their_players, my_gain, their_gain)
    """

    my_roster = list(my_team.roster)
    my_base = evaluator.value(my_roster)

    trades = []
    for team in other_teams:
        their_roster = list(team.roster)
        their_base = evaluator.value(their_roster)

        for n_give in range(1, max_size + 1):
            for n_get in range(1, max_size + 1):
                if abs(n_give - n_get) > 1:
                    continue

                for give in combinations(my_roster, n_give):
                    give_ids = {player.playerId for player in give}
                    my_keep = [
                        player
                        for player in my_roster
                        if player.playerId not in give_ids
                    ]
                    give_val = sum(ros.get(player.playerId, 0.0) for player in give)

                    for get in combinations(their_roster, n_get):
                        get_ids = {player.playerId for player in get}
                        get_val = sum(ros.get(player.playerId, 0.0) for player in get)

                        if get_val > 0 and give_val / get_val < min_value_ratio:
                            continue

                        my_gain = evaluator.value(my_keep + list(get)) - my_base
                        if my_gain < min_my_gain:
                            continue

                        their_keep = [
                            player
                            for player in their_roster
                            if player.playerId not in get_ids
                        ]
                        their_gain = (
                            evaluator.value(their_keep + list(give)) - their_base
                        )
                        if their_gain < -their_tolerance:
                            continue

                        trades.append(
                            {
                                "team": team.team_name,
                                "give": [player.name for player in give]
                                "get": [player.name for player in get]
                                "my_gain": my_gain,
                                "their_gain": their_gain,
                                "value_ratio": give_val / get_val if get_val > 0 else float("inf"),
                            }
                        )
    trades.sort(key=lambda x: x["my_gain"], reverse=True)
    return trades[:top_n]
