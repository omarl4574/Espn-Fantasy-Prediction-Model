import numpy as np
from scipy.optimize import linear_sum_assignment

from .slots import slot_accepts


class LineupEvaluator:
    """
    Value of the best possible starting lineup for a set of players, for ANY
    league layout (superflex, WR/TE flex, two flexes, no K/DST, ...).

    It's an assignment problem: players -> starting slots, maximising total
    projected ROS points, where a player may only fill a slot they're eligible
    for. Solved exactly with the Hungarian algorithm. Unfilled slots score 0,
    so a trade or drop that leaves a hole is penalised automatically.
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
                    1.0 if (slot in listed or slot_accepts(slot, player.position)) else 0.0
                    for slot in self.slot_list
                ]
            )
            self._elig[player.playerId] = row
        return row

    def _solve(self, players):
        values = np.array([max(self.ros.get(player.playerId, 0.0), 0.0) for player in players])
        eligibility = np.stack([self._eligibility(player) for player in players])
        gain = values[:, None] * eligibility                      # players x slots, 0 if ineligible
        rows, cols = linear_sum_assignment(gain, maximize=True)
        return gain, rows, cols

    def value(self, players):
        players = list(players)
        if not players or not self.slot_list:
            return 0.0
        gain, rows, cols = self._solve(players)
        return float(gain[rows, cols].sum())

    def starters(self, players):
        """[(player, slot_name)] for everyone who starts in the best lineup."""
        players = list(players)
        if not players or not self.slot_list:
            return []
        gain, rows, cols = self._solve(players)
        return [
            (players[row], self.slot_list[col])
            for row, col in zip(rows, cols)
            if gain[row, col] > 0
        ]
