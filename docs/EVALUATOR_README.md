# Evaluator guide

This project is a working Python simulation and local dashboard for battery
thermal-management controller comparison. Temperatures and cooling energy are
model outputs. No physical battery experiment or automotive ECU certification
is claimed.

## Start here

1. Read the canonical paper:
   `output/pdf/IEEE_BTMS_Research_Paper_Formatted.pdf`.
2. Use `output/pdf/BTMS_Simulation_and_Viva_Guide.pdf` for a plain-language
   explanation of the controllers, metrics, exact counts and demonstration.
3. Inspect `report/dashboard/screenshots/` for actual recorded dashboard images.
4. Follow the main README to install dependencies and launch `python -m btms.dashboard`.
5. Open Controller comparison and inspect results with the supervisor both on
   and off. Lower cost is better; higher training evaluation return is better.

## What the evidence contains

- `btms/`: plant, Gymnasium environment, controllers, training, evaluation and dashboard.
- `tests/`: plant, environment, evidence and HTTP-boundary checks.
- `data/`: retained driving traces, source provenance and fixed tuning/evaluation manifests.
- `outputs/study_20000/`: 15 runs, their configurations, metadata, TensorBoard
  events, resume pointers, 30 intermediate/final model snapshots and final evaluations.
- `report/results/`: original per-episode outcomes, comparisons, plots,
  parameter cross-check, PID tuning and deployment measurements.
- `report/dashboard/`: recorded tests, 288-outcome reproduction, one MPC
  spot-check, browser checks, screenshots and actual recorded rollout replays.
- `deliverables/`: manuscript source and references, plus supplementary reports/slides.
- `report/paper_revision/`: canonical-paper validation and figure sources.

The canonical paper is the current result interpretation. Supplementary rebuilt
DOCX/PPTX files received structural checks; their layout still needs review in
Word/PowerPoint. `PLAN.md` is historical and includes proposals superseded by the
implemented PPO/SAC/TD3 study. The four WPR pages use retrospective milestone
grouping with reporting dates left unconfirmed.

## Counts and findings

- PPO, SAC and TD3: 5 independent training seeds per algorithm, 15 final policies.
- SAC/TD3: 20,000 environment steps per run. PPO: 20,480 per run. Total: 302,400.
- Each learned policy: 8 fixed evaluation cases in each of 2 supervision modes.
- Final outcomes: 240 RL plus 64 baseline = 304. Reproduction checks are not new
  independent study outcomes.
- Recorded test report: 15 passed on 27 October 2026. The full non-MPC final
  evaluation set (288 outcomes) reproduced; only one MPC spot-check was rerun.
- Supervised mean cost: sampling MPC 1618.36, PID 1737.38, TD3 1750.04,
  SAC 1768.50 and PPO 1841.61. Lower is better.
- Learned methods do not beat tuned PID at the saved budget and violate the
  15-45 C band without supervision. Zero supervised violations do not prove
  intrinsic learned-policy safety.

## Reproduction

Run from the project root, using the tested Python dependency pins:

```text
python -m pytest -q tests/test_plant.py tests/test_env.py tests/test_dashboard.py
python -m btms.dashboard.evidence
python -m btms.dashboard
```

For a fresh final-evaluation replay, run `python -m btms.dashboard.verify --full`.
This excludes sampling MPC; it does not retrain policies. For a portable recorded
viewer, run `python -m btms.dashboard.export` and serve its `dashboard-site/`
directory with `python -m http.server 8766 --bind 127.0.0.1`. A static viewer
cannot run fresh Python simulations.

Replay buffers are deliberately omitted from the curated repository because
they occupy roughly 480 MB and are unnecessary for policy inference and final
evaluation. Training can be started afresh. Exact off-policy training resumption
requires the original replay buffers in addition to the retained model/RNG state.

## Sharing status

Public repository: https://github.com/Harshit3929/rl-battery-thermal-management

Google Drive sharing remains pending. The public repository provides source,
checkpoints, screenshots and documentation; it does not host fresh Python
simulations. Localhost addresses and filesystem paths require local execution.
