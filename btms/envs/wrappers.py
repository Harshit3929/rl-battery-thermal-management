"""Frozen shared observation calibration keeps preprocessing identical across workers."""
import gymnasium as gym
import numpy as np
from btms.utils.normalizer import RunningMeanStd


class NormalizeObservation(gym.ObservationWrapper):
    def __init__(self, env, statistics):
        super().__init__(env)
        self.normalizer = RunningMeanStd(env.observation_space.shape[0])
        self.normalizer.load_state(statistics)
        self.observation_space = gym.spaces.Box(-self.normalizer.clip, self.normalizer.clip,
                    shape=env.observation_space.shape, dtype=np.float32)

    def observation(self, observation):
        return self.normalizer.normalize(observation)


def calibrate(preview=True):
    """Collect only training conditions; freeze before any learned comparison."""
    from btms.envs.btms_env import BTMSEnv
    from btms.analysis.evaluate import manifest
    statistics = RunningMeanStd(12 if preview else 10)
    rng = np.random.default_rng(200)
    for spec in manifest('tuning'):
        env = BTMSEnv(spec['scenario'], preview=preview, episode=spec['episode'])
        obs, _ = env.reset(seed=spec['seed'])
        statistics.update(obs)
        while True:
            obs, _, term, trunc, _ = env.step(rng.uniform(0,1,3))
            statistics.update(obs)
            if term or trunc: break
    return statistics.state()
