"""Gate uses an explicitly unshielded null policy; supervision cannot hide failure."""
import json
from pathlib import Path
import numpy as np
from btms.envs.btms_env import BTMSEnv


def rollout(scenario, action, shield=False):
    env = BTMSEnv(scenario, shield=shield)
    _, meta = env.reset(seed=0)
    total = dict(scenario=scenario, shield=shield, action=list(action),
                 violation_seconds=0, shield_seconds=0, aux_wh=0., cost=0.,
                 max_temperature_c=-np.inf, spatial_delta_c=0., energy_residual_j=0.)
    while True:
        _, _, term, trunc, info = env.step(action)
        for key in ['violation_seconds', 'shield_seconds', 'aux_wh', 'cost', 'energy_residual_j']:
            total[key] += info[key]
        for key in ['max_temperature_c', 'spatial_delta_c']:
            total[key] = max(total[key], info[key])
        if term or trunc:
            total.update(duration_s=env.elapsed, termination_reason=info['termination_reason'],
                         cycle_provenance=meta['cycle_provenance'])
            break
    return total


def main():
    rows = [rollout(name, action) for name in ['mild', 'hot', 'fastcharge']
            for action in ([0, 0, 0], [1, 1, 1])]
    gate = all(r['violation_seconds']>0 for r in rows
               if r['scenario'] in ['hot', 'fastcharge'] and r['action']==[0, 0, 0])
    destination = Path(__file__).resolve().parents[2]/'report'/'results'
    destination.mkdir(parents=True, exist_ok=True)
    result = dict(hardness_passed=gate, runs=rows)
    (destination/'hardness_gate.json').write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))
    if not gate:
        raise SystemExit('Hardness gate failed: do not proceed to comparisons/training')


if __name__ == '__main__':
    main()
