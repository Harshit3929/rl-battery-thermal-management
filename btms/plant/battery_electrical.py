"""First-order Thevenin pack; positive current means discharge.

The RC resistor dissipates v_rc squared / R1, not instantaneous I squared R1.
Their difference stores energy in the polarization capacitor during transients.
OCV and equivalent pulse resistances are calibrated offline to Chen2020 SPMe
(96s34p). The 30 s RC time constant and temperature coefficient are assumptions.
"""
from dataclasses import dataclass
import numpy as np


@dataclass
class Electrical:
    soc: float = 0.8
    v_rc: float = 0.0
    capacity_ah: float = 170.0
    series_cells: int = 96
    r0_ref: float = 0.06678752651630242
    r1: float = 0.043362519
    tau_s: float = 30.0

    def ocv(self):
        return self.series_cells * float(np.interp(self.soc, [0.0, 0.05, 0.1, 0.2, 0.4, 0.5, 0.6, 0.8, 0.95, 1.0], [2.5, 3.109445952126028, 3.2959070147319545, 3.4851888247402734, 3.6670066069871456, 3.750873608447337, 3.8405766683764937, 4.042080001281208, 4.123552853492771, 4.2]))

    def resistance(self, temperature_c):
        cell_r = float(np.interp(self.soc, [0.0, 0.05, 0.1, 0.2, 0.4, 0.5, 0.6, 0.8, 0.95, 1.0], [0.030901280953549916, 0.030901280953549916, 0.028541441781176236, 0.026012421351632575, 0.023967257103468587, 0.02365391564119044, 0.0236790170395218, 0.02485432205094904, 0.02755792239889372, 0.02755792239889372]))
        return cell_r * self.series_cells / 34 * np.exp(1800 * (1 / (temperature_c + 273.15) - 1 / 298.15))

    def current_for_power(self, power_w, temperature_c):
        voltage = self.ocv() - self.v_rc
        resistance = self.resistance(temperature_c)
        discriminant = voltage**2 - 4 * resistance * power_w
        if discriminant < 0:
            raise ValueError('Demand exceeds Thevenin maximum power')
        return 2 * power_w / (voltage + np.sqrt(discriminant))

    def step(self, current_a, temperature_c, dt):
        decay = np.exp(-dt / self.tau_s)
        steady = current_a * self.r1
        transient = self.v_rc - steady
        # Exact integral of v_rc(t)^2 / R1 for constant current over this step.
        rc_j = (steady**2 * dt + 2 * steady * transient * self.tau_s * (1-decay)
                + transient**2 * self.tau_s / 2 * (1-decay**2)) / self.r1
        heat_j = current_a**2 * self.resistance(temperature_c) * dt + rc_j
        self.v_rc = steady + transient * decay
        self.soc -= current_a * dt / (3600 * self.capacity_ah)
        return heat_j
