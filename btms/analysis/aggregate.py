"""Phase 5 - aggregate runs into report-ready tables and plots.

Walks an outputs/ tree, reads each run's ``.hydra/config.yaml`` (so grouping is by
true config, not directory name) and its ``eval/return`` TensorBoard scalar, then:
  * groups runs by (algo, scenario) across seeds,
  * writes a summary CSV and a LaTeX table (final + best return, mean +/- std), and
  * saves one learning-curve figure per scenario (a line per algorithm,
    mean over seeds with a std band).

Usage:
    python -m btms.analysis.aggregate --root outputs --out report/results
"""
from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from omegaconf import OmegaConf
from tensorboard.backend.event_processing import event_accumulator


def read_eval_curve(run_dir: Path):
    values = {}
    for event in sorted(run_dir.glob('tensorboard/**/events.out.tfevents.*')):
        ea = event_accumulator.EventAccumulator(str(event), size_guidance={'scalars': 0})
        ea.Reload()
        if 'eval/return' in ea.Tags().get('scalars', []):
            for record in ea.Scalars('eval/return'):
                values[record.step] = record.value
    if not values:
        return None
    steps = sorted(values)
    return np.array(steps), np.array([values[step] for step in steps])


def collect_runs(root: Path):
    """Yield dicts: {algo, scenario, seed, steps, vals} for each run under root."""
    runs = []
    for cfg_path in root.glob("**/.hydra/config.yaml"):
        run_dir = cfg_path.parent.parent
        try:
            cfg = OmegaConf.load(cfg_path)
        except Exception:
            continue
        curve = read_eval_curve(run_dir)
        if curve is None:
            continue
        agent = cfg.agent.name
        cond = cfg.scenario.name
        runs.append({
            "algo": agent, "scenario": cond, "seed": int(cfg.seed),
            "steps": curve[0], "vals": curve[1], "run_dir": str(run_dir),
        })
    return runs


def _final_and_best(vals: np.ndarray, tail: int = 5):
    return float(vals[-tail:].mean()), float(vals.max())


def summarize(runs):
    groups = defaultdict(list)
    for r in runs:
        groups[(r["algo"], r["scenario"])].append(r)
    rows = []
    for (agent, cond), rs in sorted(groups.items()):
        finals, bests = [], []
        for r in rs:
            f, b = _final_and_best(r["vals"])
            finals.append(f); bests.append(b)
        rows.append({
            "algo": agent, "scenario": cond,
            "n_seeds": len(rs),
            "final_mean": np.mean(finals), "final_std": np.std(finals, ddof=1) if len(finals)>1 else float("nan"),
            "best_mean": np.mean(bests), "best_std": np.std(bests, ddof=1) if len(bests)>1 else float("nan"),
        })
    return rows


def write_csv(rows, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["algo", "scenario", "n_seeds",
                                          "final_mean", "final_std", "best_mean", "best_std"])
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print(f"saved {path}")


def write_latex(rows, path: Path):
    lines = [
        r"\begin{tabular}{llrrr}", r"\toprule",
        r"Algorithm & Scenario & Seeds & Final return & Best return \\", r"\midrule",
    ]
    for r in rows:
        lines.append(
            f"{r['algo']} & {r['scenario'].replace('_', ' ')} & {r['n_seeds']} & "
            f"${r['final_mean']:.0f} \\pm {r['final_std']:.0f}$ & "
            f"${r['best_mean']:.0f} \\pm {r['best_std']:.0f}$ \\\\"
        )
    lines += [r"\bottomrule", r"\end{tabular}"]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines))
    print(f"saved {path}")


def plot_curves(runs, out_dir: Path):
    by_cond = defaultdict(lambda: defaultdict(list))
    for r in runs:
        label = r["algo"]
        by_cond[r["scenario"]][label].append(r)
    out_dir.mkdir(parents=True, exist_ok=True)
    for pomdp, groups in by_cond.items():
        plt.figure(figsize=(7, 4.5))
        for label, rs in sorted(groups.items()):
            # Compare at identical actual timesteps, not merely row positions.
            steps = rs[0]['steps']
            for run in rs[1:]:
                steps = np.intersect1d(steps, run['steps'])
            if not len(steps):
                continue
            stack = np.stack([np.interp(steps, r['steps'], r['vals']) for r in rs])
            mean = stack.mean(0)
            std = stack.std(0, ddof=1) if len(rs)>1 else np.zeros_like(mean)
            plt.plot(steps, mean, label=f"{label} (n={len(rs)})")
            plt.fill_between(steps, mean - std, mean + std, alpha=0.2)
        plt.xlabel("env steps"); plt.ylabel("eval return")
        plt.title(f"BTMS - {pomdp}")
        plt.legend(); plt.grid(alpha=0.3); plt.tight_layout()
        p = out_dir / f"curve_{pomdp}.png"
        plt.savefig(p, dpi=150); plt.close()
        print(f"saved {p}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="outputs")
    ap.add_argument("--out", default="report/results")
    args = ap.parse_args()
    root, out = Path(args.root), Path(args.out)

    runs = collect_runs(root)
    if not runs:
        print(f"no runs with eval/return found under {root}")
        return
    print(f"found {len(runs)} runs")
    rows = summarize(runs)
    write_csv(rows, out / "summary.csv")
    write_latex(rows, out / "summary_table.tex")
    plot_curves(runs, out)
    print("\nSummary:")
    for r in rows:
        print(f"  {r['algo']:<11} {r['scenario']:<12} "
              f"final {r['final_mean']:7.1f} +/- {r['final_std']:5.1f}  (n={r['n_seeds']})")


if __name__ == "__main__":
    main()
