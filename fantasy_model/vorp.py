"""Value over replacement Player (VORP) + drop/add recommendations"""

from statistics import mean
from .config import MIN_PICKUP_GAIN


def replacement_levels(free_agents, top_n=2):
    """Replacement level per position = ROS of the best 'top_n' free agents at that position"""
    by_pos = {}
    for player in free_agents:
        by_pos.setdefault(player.position, []).append(player.playerId, 0.0)
    return {
        pos: mean(sorted(vals, reverse=True)[:top_n]) for pos, vals in by_pos.items()
    }


def vorp_table(players, ros, repl):
    """[(player, ros, replacement_level)] sorted from best to last"""
    rows = [
        (
            player,
            ros.get(player.playerId, 0.0),
            ros.get(player.playerId, 0.0) - repl.get(player.position, 0.0),
        )
        for player in players
    ]
    return sorted(rows, key=lambda x: x[2], reverse=True)


def best_drop_add(my_team, free_agents, evaluator, min_gain=MIN_PICKUP_GAIN, top_n=10):
    """
    For each free agent, find the best players to drop and the resulting change in your optimal
    lineup ROS points. VORP ranks playersL this measures whether the swap actually helps your
    lineup (dropping a bench player costs ~0)
    """

    roster = list(my_team.roster)
    base = evaluator.value(roster)

    best_per_fa = {}
    for fa in free_agents:
        for drop in roster:
            new_roster = [
                player for player in roster if player.playerId != drop.playerId
            ] + [fa]
            gain = evaluator.value(new_roster) - base
            if (
                gain >= min_gain
                and gain > best_per_fa.get(fa.playerId, (None, None, 0))[2]
            ):
                best_per_fa[fa.playerId] = (fa, drop, gain)

    return sorted(best_per_fa.values(), key=lambda x: x[2], reverse=True)[:top_n]
