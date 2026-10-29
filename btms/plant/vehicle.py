"""Speed is not battery current: road loads and regeneration connect them."""
from dataclasses import dataclass
import numpy as np


@dataclass(frozen=True)
class Vehicle:
    mass_kg: float = 1800.0
    drag_coefficient: float = 0.28
    frontal_area_m2: float = 2.3
    rolling_coefficient: float = 0.01
    air_density: float = 1.225
    drivetrain_efficiency: float = 0.90
    regen_efficiency: float = 0.65
    regen_limit_w: float = 60000.0
    accessory_w: float = 700.0

    def battery_power(self, speed_mps, acceleration_mps2, grade=0.0):
        angle = np.arctan(grade)
        force = (self.mass_kg * acceleration_mps2
                 + self.mass_kg * 9.81 * self.rolling_coefficient * np.cos(angle)
                 + 0.5 * self.air_density * self.drag_coefficient
                 * self.frontal_area_m2 * np.asarray(speed_mps)**2
                 + self.mass_kg * 9.81 * np.sin(angle))
        wheel = force * speed_mps
        return np.where(wheel >= 0, wheel / self.drivetrain_efficiency,
                        np.maximum(wheel * self.regen_efficiency,
                                   -self.regen_limit_w)) + self.accessory_w
