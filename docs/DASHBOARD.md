# RL Battery Lab

Start from the project folder with `.venv\Scripts\python.exe -B -m btms.dashboard`
and open http://127.0.0.1:8765. PowerShell users can also run
`powershell -File scripts/start_dashboard.ps1`. The backend binds only to loopback.

## Demonstration

1. Select `hot_s701`, SAC, comparison PID, training seed zero, and the supervisor.
2. Run a fresh simulation. Both controllers use the same fixed episode manifest.
3. Inspect calculated metrics and their comparison against the saved episode.
4. Scrub or play the trajectory. Playback is accelerated presentation of samples
   calculated by Python; it does not run the physics in JavaScript.
5. Disable the supervisor and rerun to expose intrinsic policy violations.
6. Open Study results, Training records, then Evidence & paper.
7. Download the run JSON and CSV, a checkpoint/configuration, and the manuscript.

No numbers are displayed for an unrun battery. Simulation failures remain
errors. All fresh runs are separate from the original study and are saved in
`report/dashboard/runs/`. Each export records exact initial conditions, original
driving provenance, actual dependency versions, model/source hashes and metrics.
Each control sample represents a five-second decision; safety and intervention
seconds are accumulated over one-second physics substeps.

The running process uses a fixed snapshot of study records, source fingerprints
and stateless learned actors to avoid repeated checkpoint loading. Restart the
server after modifying code, checkpoints or study artifacts.

## Verification

`python -B -m btms.dashboard.verify --full` captures actual pytest console output,
then reloads every saved RL actor and reruns both supervisor modes on all eight
evaluation episodes (240 runs), plus PID/null/bang-bang (48 runs). Sampling MPC
is excluded because of its substantially greater repeated optimization cost.
Without `--full`, eight SAC/PID hot/charging checks are performed. This command
does not retrain agents or alter original result files.

The audit uses three CPU workers by default (`--workers 1` through `4` are
supported). `--resume` retains completed checks only when their source
fingerprints match. `--tests-only` captures the current test execution without
starting another evaluation sweep.

Run comparisons require exact elapsed, violation and supervisor seconds.
Floating metrics use relative tolerance 1e-6 and absolute tolerance 1e-6. An
initial SAC replay showed 0.0000123 Wh energy drift and 0.0005664 cost drift;
these are retained in the recorded differences, not rounded away. Cross-runtime
float inference can differ slightly. A numerical match is not bitwise identity.

`python -B -m btms.dashboard.evidence` checks all aggregated means from original
per-episode records, fixed episode coverage, TensorBoard steps, checkpoint ZIP
integrity, manuscript result tables at their printed precision, and retained
source/CSV fingerprints. It does not assert independent historical authenticity,
validate a physical pack, verify references, or audit every document version.

The audit's aggregate rates are means of episode percentages. Episodes have
different durations, so these are not pooled fractions of all simulated seconds.
Baseline standard deviations span episodes; RL standard deviations span
training-seed means. Neither is labeled a confidence interval.

## Sharing

`python -B -m btms.dashboard.export` creates `dashboard-site/` and the ZIP in
`deliverables/`. The exported viewer contains source evidence and actual saved
rollouts. Serve the extracted folder with
`python -m http.server 8766 --bind 127.0.0.1`, then visit http://127.0.0.1:8766.
It explicitly disables fresh simulation and labels replay data as recorded.
Never open `index.html` directly: browsers block its local JSON fetches.

The live simulator needs a Python host with these dependencies and checkpoints.
Static hosting alone cannot execute PyTorch. This workspace has no verified
GitHub remote, Drive share, or public Python hosting URL. An exported ZIP is a
shareable artifact, not proof of evaluator access to a hosted link. Validate any
eventual shared link while signed out.

Source synchronization remains owned by Harshit's SessionEnd/Stop hook. No manual
Git commit/push is part of the dashboard workflow.
