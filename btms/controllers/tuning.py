"""Tune setpoint AND gains on training conditions using the shared scalar objective."""
import itertools
import json
import numpy as np
from btms.analysis.evaluate import RESULTS, evaluate, require_hardness


def tune():
    require_hardness()
    trials = []
    for setpoint, kp, ki in itertools.product([30.,35.,39.], [.1,.3,.6], [0.,.002]):
        parameters = dict(setpoint=setpoint,kp=kp,ki=ki,kd=0.)
        rows = evaluate('pid',split='tuning',pid_parameters=parameters)
        trials.append(dict(parameters=parameters,mean_cost=float(np.mean([r['cost'] for r in rows]))))
    best = min(trials,key=lambda trial:trial['mean_cost'])
    RESULTS.mkdir(parents=True,exist_ok=True)
    (RESULTS/'pid_tuning.json').write_text(json.dumps(dict(best_parameters=best['parameters'],
                objective='same time-integrated cost as RL; shield enabled for all tuning trials',
                split='tuning; held-out episodes excluded',trials=trials),indent=2))
    return best['parameters']
