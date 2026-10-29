"""Persist episode manifests once; every controller replays identical conditions."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
from btms.envs.btms_env import BTMSEnv, SCENARIOS
from btms.controllers.null import Null
from btms.controllers.bangbang import BangBang
from btms.controllers.pid import PID
from btms.controllers.mpc import MPC

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT/'report/results'


def manifest(split='evaluation'):
    path = ROOT/'data'/f'{split}_episodes.json'
    if path.exists():
        return json.loads(path.read_text())
    if split == 'tuning':
        rows = [dict(id=f'tune_{name}', scenario=name, seed=101, episode={})
                for name in ['mild', 'hot', 'fastcharge']]
        rows.append(dict(id='tune_hwfet', scenario='mild', seed=102, episode={'cycle':'hwfet', 'ambient_c':30., 'temperature_c':32., 'duration_s':765}))
    else:
        rows = [dict(id=f'{name}_s{seed}', scenario=name, seed=seed, episode={})
                for name in ['mild','hot','fastcharge'] for seed in [701,702]]
        rows += [dict(id='heldout_nedc', scenario='hot', seed=703,
                    episode={'cycle':'nedc','ambient_c':45.,'temperature_c':43.,'grade':.02,'duration_s':1180}),
                 dict(id='evaluation_hwfet', scenario='mild', seed=704,
                    episode={'cycle':'hwfet','ambient_c':30.,'temperature_c':32.,'duration_s':765})]
        # Initial conditions differ by seed but are fixed in this immutable manifest.
        for row in rows[:6]:
            rng = np.random.default_rng(row['seed'])
            source = SCENARIOS[row['scenario']]
            row['episode'] = {'temperature_c':float(source['temperature_c']+rng.uniform(-.5,.5)),
                              'soc':float(source['soc']+rng.uniform(-.02,.02))}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, indent=2))
    return rows


def make_controller(name, env, seed=0, pid_parameters=None):
    if name == 'null': return Null()
    if name == 'bangbang': return BangBang()
    if name == 'pid': return PID(**(pid_parameters or {}))
    if name == 'mpc': return MPC(env, seed=seed)
    raise ValueError(name)


def run_episode(controller, specification, shield=True, preview=True, pid_parameters=None, policy=None):
    env = BTMSEnv(specification['scenario'], shield=shield, preview=preview,
                  episode=specification['episode'])
    obs, meta = env.reset(seed=specification['seed'])
    agent = make_controller(controller, env, specification['seed'], pid_parameters) if policy is None else policy
    totals = dict(controller=controller, episode_id=specification['id'],
                  scenario=specification['scenario'], cycle=env.specification['cycle'], ambient_c=env.pack.ambient_c, shield=shield, preview=preview,
                  cost=0., aux_wh=0., aging_exposure_s=0., violation_seconds=0, shield_seconds=0,
                  max_temperature_c=float(max(obs[:4])), spatial_delta_c=0.)
    trace = []
    while True:
        action = agent.act(obs)
        obs, reward, term, trunc, info = env.step(action)
        for key in ['cost','aux_wh','aging_exposure_s','violation_seconds','shield_seconds']:
            totals[key] += info[key]
        for key in ['max_temperature_c','spatial_delta_c']:
            totals[key] = max(totals[key], info[key])
        trace.append(dict(time_s=env.elapsed, temperatures_c=obs[:4].tolist(),
                          raw_action=info['raw_action'], applied_action=info['applied_action']))
        if term or trunc:
            break
    totals.update(duration_s=env.elapsed,
                  violation_percent=100*totals['violation_seconds']/env.elapsed,
                  shield_firing_percent=100*totals['shield_seconds']/env.elapsed,
                  termination_reason=info['termination_reason'], final_soc=float(env.pack.electrical.soc),
                  delivered_ah=float((env.pack.electrical.soc-env.specification['soc'])*env.pack.electrical.capacity_ah),
                  cycle_provenance=meta['cycle_provenance'])
    return totals, trace


def evaluate(controller, split='evaluation', shield=True, policy=None, pid_parameters=None):
    rows = manifest(split)
    results = [run_episode(controller, row, shield=shield, policy=policy,
                           pid_parameters=pid_parameters)[0] for row in rows]
    return results


def require_hardness():
    path = RESULTS/'hardness_gate.json'
    if not path.exists() or not json.loads(path.read_text())['hardness_passed']:
        raise RuntimeError('Run and pass python -m btms.analysis.hardness first')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('overrides', nargs='*')
    parser.add_argument('--tune', action='store_true')
    parser.add_argument('--no-shield', action='store_true')
    args = parser.parse_args()
    options = dict(x.split('=',1) for x in args.overrides)
    controller = options.get('controller','null')
    require_hardness()
    pid_parameters = None
    if args.tune:
        from btms.controllers.tuning import tune
        pid_parameters = tune()
    elif controller == 'pid':
        path = RESULTS/'pid_tuning.json'
        if not path.exists():
            raise RuntimeError('Tune PID before evaluation')
        pid_parameters = json.loads(path.read_text())['best_parameters']
    if 'scenario' in options:
        spec = dict(id=options['scenario'], scenario=options['scenario'], seed=0, episode={})
        rows = [run_episode(controller, spec, shield=not args.no_shield,
                            pid_parameters=pid_parameters)[0]]
    else:
        rows = evaluate(controller, shield=not args.no_shield, pid_parameters=pid_parameters)
    RESULTS.mkdir(parents=True, exist_ok=True)
    destination = RESULTS/f'{controller}_{"raw" if args.no_shield else "shielded"}_evaluation.json'
    destination.write_text(json.dumps(rows,indent=2))
    print(json.dumps(rows,indent=2))


if __name__ == '__main__':
    main()
