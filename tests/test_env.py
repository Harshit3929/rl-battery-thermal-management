import numpy as np
from gymnasium.utils.env_checker import check_env
from btms.envs.btms_env import BTMSEnv
from btms.envs.shield import apply_shield


def test_gym_contract():
    check_env(BTMSEnv(), skip_render_check=True)


def test_shield_does_not_modify_raw_action():
    raw = np.zeros(3)
    actual, fired = apply_shield(raw, [43, 42, 41, 40])
    assert fired
    np.testing.assert_array_equal(raw, 0)
    np.testing.assert_array_equal(actual, 1)


def test_raw_and_shielded_are_explicit():
    raw = BTMSEnv('hot', shield=False)
    protected = BTMSEnv('hot', shield=True)
    raw.reset(seed=3)
    protected.reset(seed=3)
    raw_info = raw.step(np.zeros(3))[-1]
    shield_info = protected.step(np.zeros(3))[-1]
    assert raw_info['shield_seconds'] == 0
    assert shield_info['shield_seconds'] == 5
    assert shield_info['raw_action'] == [0, 0, 0]
    assert shield_info['applied_action'] == [1, 1, 1]


def test_same_episode_is_reproducible():
    a, b = BTMSEnv('mixed'), BTMSEnv('mixed')
    np.testing.assert_array_equal(a.reset(seed=8)[0], b.reset(seed=8)[0])
    for _ in range(10):
        x, y = a.step([.5, .2, .3]), b.step([.5, .2, .3])
        np.testing.assert_array_equal(x[0], y[0])
        assert x[1:] == y[1:]


def test_charge_voltage_and_checkpoint_continuation():
    env=BTMSEnv('fastcharge')
    env.reset(seed=2)
    for _ in range(200):
        env.step([.5,.2,.5])
        electrical=env.pack.electrical
        voltage=electrical.ocv()-electrical.v_rc-env.last_current*electrical.resistance(float(env.pack.thermal.temperatures_c.mean()))
        assert voltage/electrical.series_cells < 4.205
    state=env.snapshot()
    expected=env.step([.4,.3,.6])
    env.restore(state)
    actual=env.step([.4,.3,.6])
    np.testing.assert_array_equal(actual[0],expected[0])
    assert actual[1:] == expected[1:]
