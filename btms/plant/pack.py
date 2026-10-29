"""One physical seam for every controller, with explicit thermal energy accounting."""
from dataclasses import dataclass, field
import numpy as np
from .battery_electrical import Electrical
from .battery_thermal import Thermal
from .cooling import Cooling
from .aging import severity


@dataclass
class Pack:
    electrical: Electrical = field(default_factory=Electrical)
    thermal: Thermal = field(default_factory=Thermal)
    cooling: Cooling = field(default_factory=Cooling)
    ambient_c: float = 25.0

    @classmethod
    def initialized(cls, temperature_c=30.0, ambient_c=25.0, soc=.8):
        return cls(Electrical(soc=soc), Thermal(np.full(4, float(temperature_c))),
                   Cooling(temperature_c=float(temperature_c)), ambient_c)

    def step(self, current_a, action, dt=1.0):
        if not np.isfinite(dt) or dt <= 0:
            raise ValueError('dt must be positive and finite')
        action = np.asarray(action, dtype=float)
        if action.shape != (3,) or not np.all(np.isfinite(action)):
            raise ValueError('Expected three finite actuator commands')
        remaining = dt
        totals = dict(aux_j=0., heat_j=0., energy_residual_j=0., aging_exposure_s=0.)
        while remaining > 1e-10:
            sub_dt = min(1.0, remaining)
            rates = self.cooling.rates(action, self.ambient_c)
            heat_j = self.electrical.step(current_a, float(self.thermal.temperatures_c.mean()), sub_dt)
            thermal = self.thermal.step(heat_j, self.cooling.temperature_c,
                        rates['flow_kg_s'], self.cooling.cp_j_kg_k, self.ambient_c, sub_dt)
            removed_j = (rates['radiator_w']+rates['chiller_w'])*sub_dt
            pump_j = rates['pump_w']*sub_dt
            coolant_delta_j = thermal['coolant_absorbed_j']-removed_j+pump_j
            self.cooling.temperature_c += coolant_delta_j / self.cooling.capacity_j_k
            residual = (thermal['battery_stored_j']+coolant_delta_j
                        - heat_j-pump_j+thermal['ambient_rejected_j']+removed_j)
            totals['energy_residual_j'] += residual
            totals['aux_j'] += rates['aux_w']*sub_dt
            totals['heat_j'] += heat_j
            totals['aging_exposure_s'] += severity(self.thermal.temperatures_c,
                        current_a, self.electrical.capacity_ah)*sub_dt
            remaining -= sub_dt
        return dict(temperatures_c=self.thermal.temperatures_c.copy(),
                    coolant_c=self.cooling.temperature_c, soc=self.electrical.soc,
                    current_a=current_a, **totals)
