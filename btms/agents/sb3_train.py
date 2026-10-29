"""Three continuous policies, fixed evaluation episodes, and atomic resume pointers."""
from copy import deepcopy
from functools import partial
import json
import os
from pathlib import Path
import platform
import random
import time
import numpy as np
from omegaconf import OmegaConf
import torch
from stable_baselines3 import SAC, TD3, PPO
from stable_baselines3.common.callbacks import BaseCallback
from stable_baselines3.common.noise import NormalActionNoise
from stable_baselines3.common.vec_env import DummyVecEnv, SubprocVecEnv
from btms.envs.btms_env import BTMSEnv
from btms.envs.wrappers import NormalizeObservation, calibrate
from btms.utils.normalizer import RunningMeanStd
from btms.utils.seeding import seed_everything
from btms.utils.hardware import cpu_model
from btms.analysis.evaluate import evaluate, require_hardness, manifest

ALGORITHMS = dict(sac=SAC, td3=TD3, ppo=PPO)


def make_env(scenario, seed, shield, preview, statistics):
    env = NormalizeObservation(BTMSEnv(scenario,shield=shield,preview=preview),statistics)
    env.reset(seed=seed)
    return env


class PolicyController:
    def __init__(self,model,statistics):
        self.model = model
        self.normalizer = RunningMeanStd(len(statistics['mean']))
        self.normalizer.load_state(statistics)

    def act(self,observation):
        action,_ = self.model.predict(self.normalizer.normalize(observation),deterministic=True)
        return action


def checkpoint(model,env,statistics,cfg):
    directory = Path('checkpoints')/f'step_{model.num_timesteps}'
    directory.mkdir(parents=True,exist_ok=True)
    model.save(directory/'model.zip')
    if hasattr(model,'save_replay_buffer'):
        model.save_replay_buffer(directory/'replay.pkl')
    state = dict(model=str(directory/'model.zip'), replay=str(directory/'replay.pkl'),
                 statistics=statistics, config=OmegaConf.to_container(cfg,resolve=True),
                 python_rng=random.getstate(), numpy_rng=np.random.get_state(),
                 torch_rng=torch.get_rng_state(), environment=env.env_method('snapshot'),
                 num_timesteps=model.num_timesteps)
    torch.save(state,'latest.tmp')
    os.replace('latest.tmp','latest.pt')


class ExperimentCallback(BaseCallback):
    def __init__(self,env,statistics,cfg):
        super().__init__()
        self.env,self.statistics,self.cfg = env,statistics,cfg
        self.last_eval = self.last_save = 0

    def _on_training_start(self):
        self.last_eval = self.last_save = self.model.num_timesteps
        self.record_evaluation()

    def record_evaluation(self):
        controller = PolicyController(self.model,self.statistics)
        # Fixed tuning split during training; final held-out set is never optimized.
        rows = evaluate(self.cfg.agent.name,split='tuning',shield=self.cfg.shield,policy=controller)
        self.logger.record('eval/return',-np.mean([r['cost'] for r in rows]))
        self.logger.record('eval/violation_percent',np.mean([r['violation_percent'] for r in rows]))
        self.logger.record('eval/aux_wh',np.mean([r['aux_wh'] for r in rows]))
        self.logger.record('eval/shield_firing_percent',np.mean([r['shield_firing_percent'] for r in rows]))
        self.logger.dump(self.num_timesteps)
        print(f'EVAL steps={self.model.num_timesteps} return={-np.mean([r["cost"] for r in rows]):.2f}',flush=True)

    def _on_step(self):
        if self.num_timesteps-self.last_eval>=self.cfg.eval_interval:
            self.record_evaluation()
            self.last_eval=self.num_timesteps
        return True

    def _on_rollout_start(self):
        # Prior rollout has already been trained and its transitions stored.
        if self.num_timesteps-self.last_save>=self.cfg.checkpoint_interval:
            checkpoint(self.model,self.env,self.statistics,self.cfg)
            self.last_save=self.num_timesteps

    def _on_training_end(self):
        self.record_evaluation()
        checkpoint(self.model,self.env,self.statistics,self.cfg)


def train(cfg):
    require_hardness()
    if cfg.device != 'cpu':
        raise ValueError('This study is configured for CPU only')
    seed_everything(int(cfg.seed))
    manifest('evaluation')
    saved=None
    if cfg.resume_from:
        resume=Path(cfg.resume_from).resolve()
        saved=torch.load(resume,map_location='cpu',weights_only=False)
        for key in ['preview','shield','n_envs']:
            if saved['config'][key]!=cfg[key]:
                raise ValueError(f'Resume configuration mismatch: {key}')
        if saved['config']['agent']['name']!=cfg.agent.name:
            raise ValueError('Resume algorithm mismatch')
        statistics=saved['statistics']
    else:
        statistics=calibrate(cfg.preview)
    serial = [partial(make_env,cfg.scenario.name,int(cfg.seed)+i,cfg.shield,cfg.preview,statistics)
              for i in range(int(cfg.n_envs))]
    env = SubprocVecEnv(serial,start_method='spawn') if cfg.n_envs>1 else DummyVecEnv(serial)
    algorithm=ALGORITHMS[cfg.agent.name]
    if saved:
        base=resume.parent
        model=algorithm.load(base/saved['model'],env=env,device='cpu',force_reset=False)
        if (base/saved['replay']).exists():
            model.load_replay_buffer(base/saved['replay'])
        for i,state in enumerate(saved['environment']):
            env.env_method('restore',state,indices=i)
        random.setstate(saved['python_rng'])
        np.random.set_state(saved['numpy_rng'])
        torch.set_rng_state(saved['torch_rng'])
    else:
        kwargs=dict(learning_rate=cfg.agent.learning_rate,batch_size=cfg.agent.batch_size,
                    policy_kwargs=dict(net_arch=list(cfg.agent.net_arch)), device='cpu',
                    seed=int(cfg.seed),tensorboard_log='tensorboard',verbose=0)
        if cfg.agent.name=='ppo':
            kwargs.update(n_steps=cfg.agent.n_steps,n_epochs=cfg.agent.n_epochs)
        else:
            kwargs.update(buffer_size=cfg.agent.buffer_size,learning_starts=cfg.agent.learning_starts,
                          train_freq=1,gradient_steps=1)
        if cfg.agent.name=='td3':
            kwargs['action_noise']=NormalActionNoise(np.zeros(3),np.ones(3)*cfg.agent.action_noise_sigma)
        model=algorithm('MlpPolicy',env,**kwargs)
    metadata=dict(cpu=cpu_model(),platform=platform.platform(),python=platform.python_version(),
                  torch=torch.__version__,n_envs=cfg.n_envs,algo=cfg.agent.name,
                  seed=cfg.seed,training_cycles=['udds','hwfet','us06'],held_out_cycle='nedc',
                  source_revision='see recorded configuration and report/results validation artifacts')
    Path('metadata.json').write_text(json.dumps(metadata,indent=2))
    start=time.perf_counter()
    callback=ExperimentCallback(env,statistics,cfg)
    try:
        remaining=max(0,int(cfg.total_steps)-model.num_timesteps)
        if remaining:
            model.learn(total_timesteps=remaining,callback=callback,reset_num_timesteps=not bool(saved),
                        tb_log_name='run')
        else:
            checkpoint(model,env,statistics,cfg)
        policy=PolicyController(model,statistics)
        for shield in [False,True]:
            rows=evaluate(cfg.agent.name,shield=shield,policy=policy)
            Path(f'evaluation_{"shielded" if shield else "raw"}.json').write_text(json.dumps(rows,indent=2))
        metadata.update(wall_time_s=time.perf_counter()-start,completed_steps=model.num_timesteps)
        Path('metadata.json').write_text(json.dumps(metadata,indent=2))
    finally:
        env.close()
