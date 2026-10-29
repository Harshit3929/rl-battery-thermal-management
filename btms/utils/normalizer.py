"""NumPy port of SAiDL's Chan-parallel observation normalizer.

Keep raw replay observations so old samples use the current statistics. Freeze
updates during evaluation and save statistics with the policy.
"""
import numpy as np


class RunningMeanStd:
    def __init__(self, dim: int, epsilon: float = 1e-4, clip: float = 10.0):
        self.mean = np.zeros(dim, dtype=np.float64)
        self.var = np.ones(dim, dtype=np.float64)
        self.count = float(epsilon)
        self.clip = float(clip)

    def update(self, x):
        x = np.atleast_2d(np.asarray(x, dtype=np.float64))
        if x.shape[0] == 0:
            return
        delta = x.mean(axis=0) - self.mean
        n = x.shape[0]
        total = self.count + n
        self.mean += delta * n / total
        m2 = self.var * self.count + x.var(axis=0) * n
        m2 += delta**2 * self.count * n / total
        self.var = m2 / total
        self.count = total

    def normalize(self, x):
        return np.clip((x - self.mean) / np.sqrt(self.var + 1e-8),
                       -self.clip, self.clip).astype(np.float32)

    def state(self):
        return dict(mean=self.mean.copy(), var=self.var.copy(),
                    count=self.count, clip=self.clip)

    def load_state(self, state):
        self.mean = np.asarray(state['mean'], dtype=np.float64).copy()
        self.var = np.asarray(state['var'], dtype=np.float64).copy()
        self.count = float(state['count'])
        self.clip = float(state.get('clip', self.clip))
