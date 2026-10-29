import numpy as np


class Null:
    def act(self, observation):
        return np.zeros(3)
