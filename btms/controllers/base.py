from typing import Protocol
import numpy as np


class Controller(Protocol):
    def act(self, observation: np.ndarray) -> np.ndarray: ...
