"""Conservative override, explicitly not a mathematical safety guarantee."""
import numpy as np


def apply_shield(action, temperatures_c, threshold_c=42.0):
    raw = np.clip(np.asarray(action, dtype=float), 0, 1)
    fired = bool(np.max(temperatures_c) >= threshold_c)
    return (np.ones(3) if fired else raw.copy()), fired
