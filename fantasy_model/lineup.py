import numpy as np
from scipy.optimize import linear_sum_assignment
from .slots import slots_accepts


class LineupEvaluator:
    """
    Value of the best possible starting lineup for a set of players, for any league layout.
    It's an assignment problem: players -> starting slots, maximising total projected ROS
    points, where a player may only fill a slot they are eligible for. Solved exactly with
    the Hungarian algorithm. Unfilled slots score 0, so a trade or drop that leaves a hole
    is penalised automatically
    """

    def __init__(self, slots, ros):
        self.ros = ros
        self.slot_list = [name for name, n in slots.items() for _ in range(n)]
        self._elig = {}

    def _eligibility(self, player):
        row = self._elig.get(player.playerId)
        if row is None:
            listed = set(getattr(player, "eligibleSlots", None) or [])
            row = np.array(
                [
                    1.0 if (s in listed or slots_accepts(s, player.positions)) else 0.0
                    for s in self.slot_list
                ]
            )
            self._elig[player.playerId] = row

        return row

    def value(self, players):
        players = list(players)
        if not players or not self.slot_list:
            return 0.0

        vals = np.array([max(self.ros.get(p.playerId, 0.0), 0.0) for p in players])
        elig = np.stack([self._eligibility(p) for p in players])
        gain = vals[:, None] * elig
        rows, cols = linear_sum_assignment(gain, maximize=True)

        return float(gain[rows, cols].sum())
