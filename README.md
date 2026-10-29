# RL battery thermal management

A simulation-based CPU study of pump, fan and chiller control for a four-node EV
battery model. Saved PPO, SAC and TD3 policies are compared with PID, bang-bang,
null and sampling MPC. The saved learned policies do not beat tuned PID on
shielded mean cost and depend on the supervisor for the tested safety outcomes.

Public repository: https://github.com/Harshit3929/rl-battery-thermal-management

For assessment, start with the [evaluator guide](docs/EVALUATOR_README.md).
It maps the implementation, trained policies, experiments, screenshots and
canonical documents to their evidence. The saved study contains 15 final RL
policies and 304 final evaluation outcomes; 288 non-MPC outcomes were reproduced.

Launch the research dashboard from this folder:

```powershell
.venv\Scripts\python.exe -B -m btms.dashboard
```

Open **http://127.0.0.1:8765**. The dashboard executes the existing Python plant
and saved controllers; it does not invent samples or overwrite the study.
It includes fresh paired simulations, recorded results, actual TensorBoard
curves, checkpoint downloads, paper-table consistency checks and source hashes.
See [dashboard and evidence instructions](docs/DASHBOARD.md).

The corrected canonical English paper is
`output/pdf/IEEE_BTMS_Research_Paper_Formatted.pdf` (27 October 2026, nine pages,
fifteen references). Its editable source and verified bibliography are in
`deliverables/`. Rebuild with `python scripts/build_research_paper.py` and check
with `python scripts/check_research_paper.py`; see
[paper submission notes](deliverables/IEEE_BTMS_Submission_Notes.md).

Capture current tests and reproduce every learned-policy evaluation plus the
inexpensive baselines (sampling MPC explicitly excluded):

```powershell
.venv\Scripts\python.exe -B -m btms.dashboard.verify --full
.venv\Scripts\python.exe -B -m btms.dashboard.evidence
.venv\Scripts\python.exe -B -m btms.dashboard.export
```

The export creates `deliverables/RL_Battery_Lab_Evidence.zip`, a portable viewer
with saved evidence and explicitly labeled recorded-run replays. Fresh Python
simulation requires the local server. Google Drive sharing and a hosted live
simulation URL remain pending. The public repository provides the source and
saved evidence; the localhost address below is for local execution only.

The original dependency setup is:

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install torch --index-url https://download.pytorch.org/whl/cpu
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m pytest tests/test_plant.py
.venv\Scripts\python -m btms.plant.drive_cycles --report
```

On macOS/Linux, use `.venv/bin/python` instead of `.venv\Scripts\python`.
The retained study uses Python 3.13 and the dependency versions recorded in
`requirements.txt`. The repository includes model checkpoints and normalization
state required for saved-policy simulation. Replay buffers are omitted from the
curated upload; fresh training and inference remain available, but exact
off-policy training resumption requires the original buffers.

Official source files and provenance are checked in. To refresh them explicitly:
`python -m btms.plant.drive_cycles --download --report`.

Read [the architecture](docs/ARCHITECTURE.md) and
[current validation status](docs/IMPLEMENTATION_STATUS.md) before interpreting
results. The original [plan](PLAN.md) is retained as the implementation brief.
