"""Four modules exchange heat with each other and serially flowing coolant."""
from dataclasses import dataclass, field
import numpy as np


@dataclass
class Thermal:
    temperatures_c: np.ndarray = field(default_factory=lambda: np.full(4, 30.0))
    capacity_per_node_j_k: float = 60000.0
    ambient_ua_per_node: float = 4.0
    neighbor_conductance_w_k: float = 12.0
    coolant_ua_per_node: float = 250.0

    def step(self, heat_j, coolant_c, flow_kg_s, coolant_cp, ambient_c, dt):
        temperatures = self.temperatures_c
        coolant_w = np.zeros(4)
        inlet = coolant_c
        flow_capacity = flow_kg_s * coolant_cp
        if flow_capacity > 0:
            effectiveness = -np.expm1(-self.coolant_ua_per_node / flow_capacity)
            for i in range(4):
                coolant_w[i] = flow_capacity * effectiveness * (temperatures[i]-inlet)
                inlet += coolant_w[i] / flow_capacity
        ambient_w = self.ambient_ua_per_node * (temperatures-ambient_c)
        exchange = self.neighbor_conductance_w_k * np.diff(temperatures)
        conduction = np.zeros(4)
        conduction[:-1] += exchange
        conduction[1:] -= exchange
        # Equal modules: downstream variation arises from coolant warming itself.
        delta_j = heat_j / 4 + dt * (conduction-coolant_w-ambient_w)
        self.temperatures_c = temperatures + delta_j / self.capacity_per_node_j_k
        return dict(coolant_absorbed_j=float(coolant_w.sum()*dt),
                    ambient_rejected_j=float(ambient_w.sum()*dt),
                    battery_stored_j=float(delta_j.sum()), coolant_outlet_c=float(inlet))
