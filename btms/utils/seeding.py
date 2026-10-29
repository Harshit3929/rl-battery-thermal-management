"""Seed each experiment explicitly; workers receive distinct derived seeds."""
import random
import numpy as np


def seed_everything(seed: int):
    random.seed(seed)
    np.random.seed(seed)
    try:
        import torch
        torch.manual_seed(seed)
        torch.set_num_threads(1)
    except ImportError:
        pass
