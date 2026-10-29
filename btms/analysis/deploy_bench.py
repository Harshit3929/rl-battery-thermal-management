"""Measure this CPU's inference headroom; never extrapolate to an automotive ECU."""
import argparse
import json
from pathlib import Path
import time
import numpy as np
import onnxruntime as ort
from onnxruntime.quantization import quantize_dynamic, QuantType
import torch
from btms.agents.sb3_train import ALGORITHMS
from btms.analysis.evaluate import manifest, run_episode
from btms.envs.btms_env import BTMSEnv
from btms.controllers.mpc import MPC
from btms.utils.hardware import cpu_model


class ExportPolicy(torch.nn.Module):
    def __init__(self,model,statistics,algo):
        super().__init__()
        self.policy=model.policy
        self.algo=algo
        self.register_buffer('mean',torch.tensor(statistics['mean'],dtype=torch.float32))
        self.register_buffer('std',torch.sqrt(torch.tensor(statistics['var'],dtype=torch.float32)+1e-8))
        self.clip=float(statistics['clip'])

    def forward(self,observation):
        normalized=torch.clamp((observation-self.mean)/self.std,-self.clip,self.clip)
        action=self.policy._predict(normalized,deterministic=True)
        if self.algo in ['sac','td3']:
            action=(action+1)/2
        return torch.clamp(action,0,1)


class RuntimePolicy:
    def __init__(self,session):
        self.session=session

    def act(self,observation):
        return self.session.run(None,{'observation':np.asarray(observation,dtype=np.float32)[None]})[0][0]


def timings(function,observation,repeats=500):
    for _ in range(30): function(observation)
    samples=[]
    for _ in range(repeats):
        start=time.perf_counter_ns()
        function(observation)
        samples.append((time.perf_counter_ns()-start)/1e6)
    p50,p95,p99=np.percentile(samples,[50,95,99])
    return dict(median_ms=float(p50),p95_ms=float(p95),p99_ms=float(p99),
                headroom_at_10hz=float(100/p99),repeats=repeats)


def benchmark(checkpoint):
    checkpoint=Path(checkpoint).resolve()
    state=torch.load(checkpoint,map_location='cpu',weights_only=False)
    algo=state['config']['agent']['name']
    model=ALGORITHMS[algo].load(checkpoint.parent/state['model'],device='cpu')
    torch.set_num_threads(1)
    exported=ExportPolicy(model,state['statistics'],algo).eval()
    env=BTMSEnv('hot')
    observation,_=env.reset(seed=704)
    output=checkpoint.parent/'deployment'
    output.mkdir(exist_ok=True)
    onnx_path=output/'policy.onnx'
    with torch.no_grad():
        torch.onnx.export(exported,torch.from_numpy(observation[None]),str(onnx_path),
                          input_names=['observation'],output_names=['action'],
                          dynamic_axes={'observation':{0:'batch'},'action':{0:'batch'}},
                          opset_version=17,dynamo=False)
    quantized=output/'policy_int8.onnx'
    quantize_dynamic(str(onnx_path),str(quantized),weight_type=QuantType.QInt8)
    options=ort.SessionOptions()
    options.intra_op_num_threads=1
    options.inter_op_num_threads=1
    sessions={label:ort.InferenceSession(str(path),sess_options=options,providers=['CPUExecutionProvider'])
              for label,path in [('onnx',onnx_path),('int8',quantized)]}
    def torch_predict(obs):
        with torch.no_grad():
            return exported(torch.from_numpy(obs[None])).numpy()[0]
    reference=torch_predict(observation)
    rows=[dict(runtime='pytorch',**timings(torch_predict,observation))]
    evaluations={}
    for label,session in sessions.items():
        policy=RuntimePolicy(session)
        rows.append(dict(runtime=label,**timings(policy.act,observation),
                   footprint_kb=(onnx_path if label=='onnx' else quantized).stat().st_size/1024,
                   maximum_action_error=float(np.max(np.abs(policy.act(observation)-reference)))))
        evaluations[label]=[run_episode(algo,spec,policy=policy)[0] for spec in manifest()]
    mpc=MPC(env,seed=704)
    rows.append(dict(runtime='sampling_mpc',**timings(mpc.act,observation,repeats=50)))
    result=dict(cpu=cpu_model(),torch_version=torch.__version__,onnxruntime_version=ort.__version__,
                algo=algo,seed=state['config']['seed'],control_period_ms=100,
                interpretation='Measured laptop CPU headroom only; plant controller currently runs every 5 s.',
                rows=rows,quantized_quality_evaluation=evaluations)
    (output/'benchmark.json').write_text(json.dumps(result,indent=2))
    print(json.dumps({k:v for k,v in result.items() if k!='quantized_quality_evaluation'},indent=2))
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--checkpoint',required=True)
    benchmark(parser.parse_args().checkpoint)
