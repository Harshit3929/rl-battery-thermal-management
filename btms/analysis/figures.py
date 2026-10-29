"""Create report figures from fixed, already-completed experiment records.

This module never trains a policy.  It reads the aggregated controller results
and, for the trace figure only, replays the saved SAC seed-0 and tuned PID on
one fixed held-out episode.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch

from btms.agents.sb3_train import ALGORITHMS, PolicyController
from btms.analysis.evaluate import manifest, run_episode


ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "report" / "results"
SAC_RUN = ROOT / "outputs" / "study_20000" / "sac_mixed_seed0" / "2026-09-21_12-25-46-068193"


def _save(fig: plt.Figure, name: str) -> None:
    fig.tight_layout()
    fig.savefig(RESULTS / name, dpi=180)
    plt.close(fig)


def controller_comparison(rows: pd.DataFrame) -> None:
    shielded = rows[(rows["shield"] == True) & rows["algo"].isin(["pid", "ppo", "sac", "td3"])]
    order = ["pid", "ppo", "sac", "td3"]
    shielded = shielded.set_index("algo").loc[order].reset_index()
    labels = ["PID tuned", "PPO", "SAC", "TD3"]
    fig, axes = plt.subplots(1, 3, figsize=(12, 3.7))
    axes[0].bar(labels, shielded["cost_mean"], yerr=shielded["cost_std"], color="#285E8E", capsize=3)
    axes[0].set_title("Shielded integrated cost")
    axes[0].set_ylabel("mean cost")
    axes[1].bar(labels, shielded["aux_wh_mean"], yerr=shielded["aux_wh_std"], color="#5B9BD5", capsize=3)
    axes[1].set_title("Auxiliary energy")
    axes[1].set_ylabel("Wh per episode")
    axes[2].bar(labels, shielded["shield_firing_percent_mean"], yerr=shielded["shield_firing_percent_std"], color="#C55A11", capsize=3)
    axes[2].set_title("Shield intervention")
    axes[2].set_ylabel("percent of steps")
    for ax in axes:
        ax.tick_params(axis="x", rotation=30)
        ax.grid(axis="y", alpha=0.25)
    _save(fig, "controller_comparison_shielded.png")


def safety_comparison(rows: pd.DataFrame) -> None:
    learned = rows[rows["algo"].isin(["ppo", "sac", "td3"])].copy()
    raw = learned[learned["shield"] == False].set_index("algo").loc[["ppo", "sac", "td3"]]
    shielded = learned[learned["shield"] == True].set_index("algo").loc[["ppo", "sac", "td3"]]
    labels = ["PPO", "SAC", "TD3"]
    x = np.arange(len(labels))
    fig, ax = plt.subplots(figsize=(7.2, 4.1))
    ax.bar(x - 0.19, raw["violation_percent_mean"], 0.38, label="Unshielded violation", color="#C00000")
    ax.bar(x + 0.19, shielded["shield_firing_percent_mean"], 0.38, label="Shield firing", color="#ED7D31")
    ax.set_xticks(x, labels)
    ax.set_ylabel("percent of evaluated steps")
    ax.set_title("Safety depends on supervisory intervention")
    ax.legend()
    ax.grid(axis="y", alpha=0.25)
    _save(fig, "safety_intervention_comparison.png")


def deployment_latency() -> None:
    bench = json.loads((RESULTS / "deployment_benchmark_sac_seed0.json").read_text())
    rows = bench["rows"]
    labels = ["PyTorch", "ONNX", "INT8", "Sampling MPC"]
    values = [row["median_ms"] for row in rows]
    fig, ax = plt.subplots(figsize=(7.2, 4.1))
    ax.bar(labels, values, color=["#4472C4", "#5B9BD5", "#70AD47", "#C00000"])
    ax.set_yscale("log")
    ax.axhline(100, color="#555555", linestyle="--", linewidth=1, label="10 Hz period (100 ms)")
    ax.set_ylabel("median inference or solve time (ms, log scale)")
    ax.set_title("Laptop CPU deployment benchmark")
    ax.legend()
    ax.grid(axis="y", alpha=0.25)
    _save(fig, "deployment_latency.png")


def temperature_trace() -> None:
    state = torch.load(SAC_RUN / "latest.pt", map_location="cpu", weights_only=False)
    model = ALGORITHMS["sac"].load(SAC_RUN / state["model"], device="cpu")
    sac = PolicyController(model, state["statistics"])
    pid_parameters = json.loads((RESULTS / "pid_tuning.json").read_text())["best_parameters"]
    episode = next(row for row in manifest("evaluation") if row["id"] == "hot_s701")
    _, sac_trace = run_episode("sac", episode, shield=True, policy=sac)
    _, pid_trace = run_episode("pid", episode, shield=True, pid_parameters=pid_parameters)
    fig, ax = plt.subplots(figsize=(8.3, 4.2))
    for label, trace, color in [("SAC seed 0", sac_trace, "#4472C4"), ("Tuned PID", pid_trace, "#70AD47")]:
        time_s = [row["time_s"] for row in trace]
        maximum = [max(row["temperatures_c"]) for row in trace]
        ax.plot(time_s, maximum, label=label, color=color)
    ax.axhspan(15, 45, color="#D9EAD3", alpha=0.55, label="Safe band")
    ax.axhline(42, color="#C00000", linestyle="--", linewidth=1, label="Shield threshold (42 C)")
    ax.set_xlabel("time (s)")
    ax.set_ylabel("maximum node temperature (C)")
    ax.set_title("Hot US06 episode with supervisor enabled")
    ax.set_ylim(15, 47)
    ax.legend(ncol=2, fontsize=8)
    ax.grid(alpha=0.25)
    _save(fig, "temperature_trace_hot_s701.png")


def main() -> None:
    global RESULTS
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(RESULTS))
    args = parser.parse_args()
    RESULTS = Path(args.out)
    rows = pd.read_csv(RESULTS / "controller_comparison.csv")
    controller_comparison(rows)
    safety_comparison(rows)
    deployment_latency()
    temperature_trace()
    print("saved report figures to", RESULTS)


if __name__ == "__main__":
    main()
