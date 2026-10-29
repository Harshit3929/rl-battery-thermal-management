"""Conservation and limiting cases matter more than controller-shaped tests."""
import numpy as np
import pytest
from btms.plant.pack import Pack
from btms.plant.battery_electrical import Electrical
from btms.utils.normalizer import RunningMeanStd


def test_thermal_energy_conservation():
    pack = Pack.initialized(38, 32)
    for _ in range(100):
        state = pack.step(300, [.6, .5, .4], 5)
        assert abs(state['energy_residual_j']) < 1e-8


def test_heat_cooling_and_soc():
    hot = Pack.initialized(38, 25)
    cold = Pack.initialized(38, 25)
    for _ in range(600):
        off = hot.step(150, [0, 0, 0])
        on = cold.step(150, [1, 1, 1])
    assert off['temperatures_c'].mean() > 38
    assert on['temperatures_c'].mean() < 38
    assert on['soc'] < .8
    assert np.ptp(on['temperatures_c']) > 0


def test_equilibrium_and_charge_sign():
    pack = Pack.initialized(25, 25)
    state = pack.step(0, [0, 0, 0], 60)
    np.testing.assert_allclose(state['temperatures_c'], 25)
    assert pack.step(-100, [0, 0, 0])['soc'] > .8


def test_rc_capacitor_energy_balance():
    electrical = Electrical(soc=.5)
    current, dt = 250., 10.
    resistance = electrical.resistance(25)
    heat = electrical.step(current, 25, dt)
    cap = electrical.tau_s / electrical.r1
    stored = .5 * cap * electrical.v_rc**2
    rc_input = current**2 * electrical.r1 * (dt-electrical.tau_s*(1-np.exp(-dt/electrical.tau_s)))
    assert heat+stored == pytest.approx(current**2*resistance*dt+rc_input)


def test_running_statistics_match_batch():
    samples = np.random.default_rng(5).normal(size=(1000, 5))
    stats = RunningMeanStd(5, epsilon=0)
    for batch in np.array_split(samples, 10):
        stats.update(batch)
    np.testing.assert_allclose(stats.mean, samples.mean(0), atol=1e-12)
    np.testing.assert_allclose(stats.var, samples.var(0), atol=1e-12)
