"""Sampling MPC is a feasible comparator, never a certified optimal bound."""
from copy import deepcopy
import numpy as np


class MPC:
    def __init__(self, env, seed=0, candidates=10, horizon=12):
        self.env, self.horizon = env, horizon
        self.rng = np.random.default_rng(seed)
        self.candidates = candidates
        self.previous = np.zeros(3)

    def act(self, observation):
        actions = [np.zeros(3), np.ones(3), self.previous.copy()]
        actions += list(self.rng.uniform(0, 1, (self.candidates-3, 3)))
        best_cost, best = np.inf, actions[0]
        for action in actions:
            simulated = deepcopy(self.env)
            cost = 0.
            for _ in range(self.horizon):
                _, reward, term, trunc, _ = simulated.step(action)
                cost -= reward
                if term or trunc:
                    break
            if cost < best_cost:
                best_cost, best = cost, action
        self.previous = np.array(best)
        return self.previous.copy()
