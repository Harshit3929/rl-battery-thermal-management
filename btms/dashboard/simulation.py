"""Fresh rollouts using BTMSEnv, original baseline classes and saved SB3 actors."""
from __future__ import annotations

import json
import math
from importlib.metadata import version
from functools import lru_cache

from .evidence import ROOT, digest, find_run, read_json, recorded_episodes, relative, stamp


@lru_cache(maxsize=15)
def load_policy(controller, training_seed):
    """Actors have no recurrent state; reuse the same frozen actor across episodes."""
    import torch
    from btms.agents.sb3_train import ALGORITHMS, PolicyController
    torch.set_num_threads(1)
    checkpoint = find_run(controller, training_seed)
    state = torch.load(checkpoint, map_location='cpu', weights_only=False)
    model_path = (checkpoint.parent / state['model']).resolve()
    if not model_path.is_relative_to(checkpoint.parent.resolve()):
        raise ValueError('Checkpoint model path leaves the saved run directory')
    model = ALGORITHMS[controller].load(model_path, device='cpu')
    agent = PolicyController(model, state['statistics'])
    info = dict(path=relative(checkpoint), sha256=digest(checkpoint),
                model_path=relative(model_path), model_sha256=digest(model_path),
                training_seed=training_seed, completed_steps=state['num_timesteps'])
    return agent, info


@lru_cache(maxsize=1)
def recorded_index():
    return {(r['controller'], r['episode_id'], r['shield'], r.get('seed')): r for r in recorded_episodes()}


@lru_cache(maxsize=1)
def source_fingerprints():
    paths = [ROOT / 'btms/envs/btms_env.py', ROOT / 'btms/envs/shield.py',
             ROOT / 'btms/dashboard/simulation.py', ROOT / 'btms/analysis/evaluate.py',
             ROOT / 'btms/agents/sb3_train.py', ROOT / 'btms/utils/normalizer.py',
             ROOT / 'data/evaluation_episodes.json', ROOT / 'report/results/pid_tuning.json']
    paths += list((ROOT / 'btms/plant').glob('*.py'))
    paths += list((ROOT / 'btms/controllers').glob('*.py'))
    return {relative(p): digest(p) for p in paths}


@lru_cache(maxsize=1)
def dependency_versions():
    return {name: version(name) for name in ('numpy', 'gymnasium', 'torch', 'stable-baselines3')}


def simulate(spec, controller, shield, training_seed=0, progress=None):
    from btms.envs.btms_env import BTMSEnv
    from btms.analysis.evaluate import make_controller
    env = BTMSEnv(spec['scenario'], shield=shield, episode=spec['episode'])
    observation, metadata = env.reset(seed=spec['seed'])
    checkpoint_info = None
    if controller in ('sac', 'ppo', 'td3'):
        agent, checkpoint_info = load_policy(controller, training_seed)
    else:
        pid = read_json(ROOT / 'report/results/pid_tuning.json')['best_parameters']
        agent = make_controller(controller, env, seed=spec['seed'], pid_parameters=pid)
    totals = dict(cost=0., aux_wh=0., aging_exposure_s=0., violation_seconds=0,
                  shield_seconds=0, max_temperature_c=float(max(observation[:4])), spatial_delta_c=0.)
    initial = dict(time_s=0, temperatures_c=observation[:4].tolist(), soc=float(observation[4]),
                   coolant_c=float(observation[8]), raw_action=None, applied_action=None,
                   cost=0., aux_wh=0., violation_seconds=0, shield_seconds=0)
    trace = [initial]
    try:
        while True:
            action = agent.act(observation)
            observation, _, terminated, truncated, info = env.step(action)
            for key in ('cost', 'aux_wh', 'aging_exposure_s', 'violation_seconds', 'shield_seconds'):
                totals[key] += info[key]
            for key in ('max_temperature_c', 'spatial_delta_c'):
                totals[key] = max(totals[key], info[key])
            trace.append(dict(time_s=env.elapsed, temperatures_c=observation[:4].tolist(),
                              soc=float(observation[4]), coolant_c=float(observation[8]),
                              demand_kw=float(observation[9]), current_a=float(env.last_current),
                              raw_action=info['raw_action'], applied_action=info['applied_action'],
                              shield_seconds_step=info['shield_seconds'], **totals))
            if progress and (len(trace) % 10 == 0 or terminated or truncated):
                progress(env.elapsed, env.specification['duration_s'], trace)
            if terminated or truncated:
                break
        totals.update(duration_s=env.elapsed, violation_percent=100*totals['violation_seconds']/env.elapsed,
                      shield_firing_percent=100*totals['shield_seconds']/env.elapsed,
                      final_soc=float(env.pack.electrical.soc), termination_reason=info['termination_reason'])
        saved = recorded_index().get((controller, spec['id'], shield,
                                      training_seed if controller in ('ppo', 'sac', 'td3') else None))
        differences = ({key: dict(fresh=totals[key], recorded=saved[key],
                                   absolute_difference=abs(totals[key]-saved[key]),
                                   matches=(totals[key] == saved[key] if key in ('violation_seconds', 'shield_seconds', 'duration_s')
                                            else math.isclose(totals[key], saved[key], rel_tol=1e-6, abs_tol=1e-6)))
                        for key in totals if key in saved and isinstance(totals[key], (float, int))}
                       if saved else {})
        return dict(kind='fresh simulation', completed_at=stamp(), controller=controller,
                    training_seed=training_seed if checkpoint_info else None,
                    episode=spec, specification=env.specification, shield=shield,
                    checkpoint=checkpoint_info, cycle_provenance=metadata['cycle_provenance'],
                    metrics=totals, trace=trace, recorded_comparison=differences,
                    comparison_tolerance=dict(relative=1e-6, absolute=1e-6, exact=['violation_seconds', 'shield_seconds', 'duration_s']),
                    reproduces_recorded_metrics=bool(differences) and all(r['matches'] for r in differences.values()),
                    dependencies=dependency_versions(), source_sha256=source_fingerprints(),
                    runtime_snapshot='Artifacts and frozen policies are cached for this process. Restart after changing code or study files.')
    finally:
        env.close()
