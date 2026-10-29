"""Relative temperature/C-rate exposure, not a calibrated lifetime prediction."""
import numpy as np


def severity(temperatures_c, current_a, capacity_ah=170.0):
    arrhenius = np.exp(30000 / 8.314 * (1 / 298.15 - 1 / (np.asarray(temperatures_c)+273.15)))
    return float(np.mean(arrhenius) * (1 + abs(current_a) / capacity_ah))
