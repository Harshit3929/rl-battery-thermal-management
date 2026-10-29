"""One-second physics under a five-second controller, with inspectable reward terms."""
from copy import deepcopy
import gymnasium as gym
from gymnasium import spaces
import numpy as np
from btms.plant.pack import Pack
from btms.plant.drive_cycles import power_trace
from .shield import apply_shield

SCENARIOS = {
    'mild': dict(cycle='udds', ambient_c=25., temperature_c=30., soc=.8, grade=0., duration_s=1365),
    'hot': dict(cycle='us06', ambient_c=43., temperature_c=43., soc=.8, grade=.06, duration_s=1800),
    'fastcharge': dict(cycle='charge', ambient_c=38., temperature_c=38., soc=.15, grade=0., duration_s=1350),
}


def objective(temperatures, aux_j, aging_exposure_s, dt):
    """Shared normalized cost: time-integrated terms stay comparable across dt."""
    violation = max(float(np.max(temperatures))-45., 0.) + max(15.-float(np.min(temperatures)), 0.)
    terms = dict(safety=(violation/5)**2, spatial=float(np.ptp(temperatures))/5,
                 energy=aux_j/(3000*dt), aging=aging_exposure_s/(5*dt))
    cost = dt * (20*terms['safety'] + terms['spatial'] + terms['energy'] + terms['aging'])
    return cost, terms


class BTMSEnv(gym.Env):
    metadata = {'render_modes': []}

    def __init__(self, scenario='mild', shield=True, preview=True, episode=None):
        super().__init__()
        self.scenario = scenario
        self.shield_enabled = shield
        self.preview = preview
        self.episode_override = episode
        self.action_space = spaces.Box(0., 1., shape=(3,), dtype=np.float32)
        self.observation_space = spaces.Box(-np.inf, np.inf, shape=(12 if preview else 10,), dtype=np.float32)
        self.control_dt = 5

    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        name = self.scenario
        if name == 'mixed':
            name = self.np_random.choice(['mild', 'hot', 'fastcharge'])
        self.specification = dict(SCENARIOS[name])
        if self.scenario == 'mixed' and name != 'fastcharge':
            self.specification['cycle'] = str(self.np_random.choice(['udds','hwfet','us06']))
        if self.episode_override:
            self.specification.update(self.episode_override)
        if options:
            self.specification.update(options)
        s = self.specification
        self.pack = Pack.initialized(s['temperature_c'], s['ambient_c'], s['soc'])
        self.elapsed = 0
        self.last_current = 0.
        if s['cycle'] == 'charge':
            self.power = None
            self.provenance = {'provenance': 'specified_charge_protocol', 'c_rate': 2.0}
        else:
            time, _, power, self.provenance = power_trace(s['cycle'], s['grade'])
            seconds = np.arange(int(time[-1])+1)
            self.power = np.interp(seconds, time, power)
        return self._observation(), {'episode': self.specification, 'cycle_provenance': self.provenance}

    def demanded_power(self, second):
        if self.power is None:
            return -2.0*self.pack.electrical.capacity_ah*self.pack.electrical.ocv()
        return float(self.power[second % len(self.power)])

    def _observation(self):
        p = self.pack
        obs = [*p.thermal.temperatures_c, p.electrical.soc,
               self.last_current/p.electrical.capacity_ah, p.ambient_c,
               float(self.power is None), p.cooling.temperature_c, self.demanded_power(self.elapsed)/1000]
        if self.preview:
            obs += [np.mean([self.demanded_power(self.elapsed+i) for i in range(30)])/1000,
                    max(self.demanded_power(self.elapsed+i) for i in range(60))/1000]
        return np.asarray(obs, dtype=np.float32)

    def step(self, action):
        raw = np.asarray(action, dtype=float)
        if raw.shape != (3,) or not np.all(np.isfinite(raw)):
            raise ValueError('Expected three finite actuator commands')
        raw = np.clip(raw, 0, 1)
        aux_j = aging = cost = 0.
        fired_count = violation_count = 0
        max_temperature = -np.inf
        max_spread = 0.
        residual = 0.
        actual = raw.copy()
        termination = False
        reason = ''
        steps = min(self.control_dt, self.specification['duration_s']-self.elapsed)
        for _ in range(steps):
            if self.shield_enabled:
                actual, fired = apply_shield(raw, self.pack.thermal.temperatures_c)
            else:
                actual, fired = raw, False
            fired_count += int(fired)
            auxiliary_w = self.pack.cooling.rates(actual, self.pack.ambient_c)['aux_w']
            if self.power is None:
                current = -2.0*self.pack.electrical.capacity_ah
                # Charge protocol tapers above 80% SoC and stops at 90%.
                current *= float(np.clip((.9-self.pack.electrical.soc)/.1, 0, 1))
                current += auxiliary_w/self.pack.electrical.ocv()
                # CC-CV: terminal voltage must not exceed 4.2 V per series cell.
                electrical = self.pack.electrical
                r0 = electrical.resistance(float(self.pack.thermal.temperatures_c.mean()))
                voltage_limited = (electrical.ocv()-electrical.v_rc-4.2*electrical.series_cells)/r0
                current = max(current, min(voltage_limited, 0.))
            else:
                current = self.pack.electrical.current_for_power(
                    self.demanded_power(self.elapsed)+auxiliary_w,
                    float(self.pack.thermal.temperatures_c.mean()))
            state = self.pack.step(current, actual)
            temps = state['temperatures_c']
            increment, terms = objective(temps, state['aux_j'], state['aging_exposure_s'], 1)
            cost += increment
            aux_j += state['aux_j']
            aging += state['aging_exposure_s']
            residual += abs(state['energy_residual_j'])
            max_temperature = max(max_temperature, float(temps.max()))
            max_spread = max(max_spread, float(np.ptp(temps)))
            violation_count += int(temps.max()>45 or temps.min()<15)
            self.last_current = current
            self.elapsed += 1
            if not .05 < self.pack.electrical.soc < .95:
                termination, reason = True, 'soc_limit'
                break
        truncated = self.elapsed >= self.specification['duration_s']
        info = dict(aux_wh=aux_j/3600, aging_exposure_s=aging, cost=cost,
                    max_temperature_c=max_temperature, spatial_delta_c=max_spread,
                    violation_seconds=violation_count, shield_seconds=fired_count,
                    raw_action=raw.tolist(), applied_action=actual.tolist(),
                    energy_residual_j=residual, elapsed_s=self.elapsed,
                    termination_reason=reason, reward_terms=terms)
        return self._observation(), -cost, termination, truncated, info

    def snapshot(self):
        return deepcopy(self.__dict__)

    def restore(self, state):
        self.__dict__.update(deepcopy(state))
