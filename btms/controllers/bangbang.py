import numpy as np


class BangBang:
    def __init__(self, high=39., low=35.):
        self.high, self.low, self.on = high, low, False

    def act(self, observation):
        maximum = max(observation[:4])
        if maximum >= self.high:
            self.on = True
        elif maximum <= self.low:
            self.on = False
        return np.ones(3) if self.on else np.zeros(3)
