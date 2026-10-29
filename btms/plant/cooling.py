"""Finite coolant inventory avoids obtaining cooling from an implicit heat sink."""
from dataclasses import dataclass
import numpy as np


@dataclass
class Cooling:
    temperature_c: float = 30.0
    capacity_j_k: float = 20000.0
    cp_j_kg_k: float = 3800.0
    max_flow_kg_s: float = 0.5
    max_chiller_w: float = 12000.0
    cop: float = 2.5

    def rates(self, action, ambient_c):
        pump, fan, valve = np.clip(action, 0, 1)
        flow = self.max_flow_kg_s * pump
        # Pump-off cannot circulate heat through the radiator or chiller.
        circulation = 1 - np.exp(-flow / 0.08)
        # Passive thermostatic radiator bypass prevents heating chilled coolant.
        radiator = circulation * (30 + 400 * fan) * max(self.temperature_c-ambient_c, 0)
        chiller = circulation * valve * self.max_chiller_w
        # Capacity fades at the lower coolant limit instead of clipping energy away.
        chiller *= float(np.clip((self.temperature_c-15) / 5, 0, 1))
        pump_w, fan_w = 150 * pump**3, 300 * fan**3
        return dict(flow_kg_s=float(flow), radiator_w=float(radiator),
                    chiller_w=float(chiller), pump_w=float(pump_w),
                    aux_w=float(pump_w+fan_w+chiller/self.cop))
