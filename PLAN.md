# RL-BTMS — rebuild plan & implementation handoff

> **For the implementing agent (Codex).** This document is self-contained — it
> assumes no prior conversation. Read it top to bottom before writing code.
> Nothing in this repo exists yet except this file.

---

## 1. What the project is

**"Reinforcement Learning-Based Dynamic Battery Thermal Management for Software
Defined Electric Vehicles"** — B.Tech CSE major project, IILM University Greater
Noida, session 2026-27. Guide: Dr. Pranav Srivastava. Team: Rishuraj Singh
(2410030738), Nihaal Sansanwal (2410031372), Harshit Parmar (2410031422),
Chaitanya Sharma (2410031341).

**The engineering problem.** An EV battery pack generates heat (mostly I²R). It
must stay roughly within 15–45 °C, and cells must stay *uniform* (spread < ~5 °C)
or the pack ages to the speed of its worst cell. Cooling is done by a coolant
pump, a radiator fan, and a refrigerant valve into a chiller — all drawing power
from the battery you're protecting. **The optimisation: keep the pack safe and
uniform while spending as little auxiliary energy as possible.**

**The thesis.** A learned policy can anticipate thermal load rather than react to
it, and — being a single forward pass — is cheap enough to run as an
OTA-updatable module on a software-defined vehicle's zonal compute, where a
model-predictive optimiser would not be.

**The claimed research gap (Phase-I §2.10):** the literature studies RL-BTMS *or*
SDV platforms, never algorithm + reward + deployment platform as one design
problem. **This gap is the project's novelty and is currently unimplemented.**

---

## 2. Why we are rebuilding

Phase I, II, III and Mid-Term reports are written and structurally sound. The code
behind the Phase-III results **no longer exists** — it was written inside a
claude.ai chat sandbox and never saved locally (both drives swept; nothing found).

Rebuilding is unavoidable, so we fix three defects that make the reported results
indefensible. **Understanding these is the whole point of the rebuild — do not
"restore" the old behaviour.**

### Defect 1 — the baseline was given a harder task
PID tracks a **30 °C set-point**; the RL agent is only penalised for leaving the
**15–45 °C band**. Those are different objectives. The reported *"95% cooling-energy
saving"* largely measures that mismatch, not agent skill.

### Defect 2 — the environment is degenerate
Reported FTP-75 cooling energy was **0.02 Wh/episode** — i.e. the agent learned
*not to cool at all*, and the environment let it stay safe anyway. **A control
problem only exists if doing nothing is unsafe.** This also explains the US06
gradient anomaly (no actuation → temperature tracks current → high |dT/dt|),
which the report misattributes to reward weighting.

### Defect 3 — the reward measures something the model cannot express
The reward penalises **inter-cell (spatial)** gradient, but the model was a
**single lumped thermal node**. `max |dT/dt|` — a *temporal* rate — was substituted
as a "proxy". Different physical quantity. The Phase-III design review asserts
"no deviations were found"; that claim cannot hold with one node.

### Secondary gaps
- Action space collapsed from 3 actuators to one scalar — removing exactly the
  multi-actuator coordination that justifies RL over PID.
- Drive cycles are **speed**-vs-time in reality; converting to current needs a
  longitudinal vehicle model. That step was skipped.
- Single seed, single run. Deep-RL results swing hugely across seeds.
- "Zero violations" was luck (a soft penalty), not a guarantee.

> **Faithfulness note:** the multi-node model and 3 actuators below are *closer*
> to Phase-I/II than the old code, which promised pump/fan/valve and inter-cell
> gradient but delivered one scalar and one node. This rebuild **shrinks** the
> design-to-code gap.

---

## 3. Existing artifacts (read-only inputs)

| Artifact | Path |
|---|---|
| Phase-I report (revised) | `C:\Users\parma\Desktop\Major_Phase1_Report_RL_Battery_Thermal_Management_revised.docx` |
| Phase-II report | `C:\Users\parma\Desktop\Phase2_Report_RL_Battery_Thermal_Management (1).docx` |
| Mid-Term report | `C:\Users\parma\Desktop\MidTerm_Evaluation_Report_RL_Battery_Thermal_Management.docx` |
| **Phase-III report** | `C:\Users\parma\AppData\Local\Packages\5319275A.WhatsAppDesktop_cv1g1gvanyjgm\LocalState\sessions\17A81346D475C71AE1B7E97B938507BB7ADB2862\transfers\2026-37\Phase3_Report_RL_Battery_Thermal_Management.docx` |
| Existing decks | `C:\Users\parma\Documents\Codex\2026-09-08\shar\outputs\*.pptx` |

Decks are Codex-authored build outputs — **copy into this repo before editing;
do not modify in place.**

---

## 4. Compute strategy — everything runs locally

**Key finding: this is an environment-bound workload, not a GPU workload.** The
policies are small MLPs; the expensive part is stepping the plant. Stable-Baselines3
itself warns that PPO/SAC with `MlpPolicy` are usually *faster on CPU*.

The machine has **12 logical cores** (verified) and an RTX 4050 (6 GB). Cloud
notebooks were considered and rejected — they offer fewer cores than this laptop
for an env-bound workload, and their GPUs buy nothing here.

**Therefore:**

- **Train on CPU.** Set `device="cpu"` in SB3; use `SubprocVecEnv` with 8–10
  workers. Profile before assuming the GPU helps — it will not for MLPs this size.
- **Benchmark inference latency on this machine only**, with the CPU model
  recorded in the output. The "automotive ECU headroom" figure is the project's
  novelty claim; it needs reproducible, known hardware behind it.
- **Still implement checkpoint/resume** (`latest.pt`, per the SAiDL pattern).
  Sweeps run for hours and laptops get closed.

### ⚠ One trap carried over from Phase-III

The original project shipped **synthetic drive cycles** purely because its sandbox
had no internet — and the report's headline numbers were computed against them.
This machine *has* internet, so Stage 3 must download the real traces. Every run
must still record cycle provenance (`real` vs `synthetic`) in its output metadata,
so a surrogate can never silently masquerade as real data again.

---

## 5. Environment (verified on this machine)

| Fact | Value | Consequence |
|---|---|---|
| Python | 3.13.14 global | needs SB3 ≥ 2.4 for py3.13 |
| `torch`, `stable-baselines3` | **absent everywhere** | must install |
| Present | numpy 2.3.2, scipy 1.18, matplotlib 3.11, pandas 3.0.5 | plant + analysis need nothing more |
| GPU | RTX 4050 Laptop, 6141 MiB | not needed; train CPU |
| git | 2.55.0 | `git init`, **local only, no remote** |

Install **CPU torch** (small, fast, no CUDA risk). The SAiDL `requirements.txt`
documents the cu128 route if a GPU build is ever wanted — it won't be.

---

## 6. Reuse from the sibling repo — do not rewrite

`D:\Coding\Reinforcement Learning SAiDL` is the same author's RL project. Match its
conventions, and port two files outright:

- **`seqrl/td3/normalizer.py` → `btms/utils/normalizer.py`.** Streaming
  Chan-parallel `RunningMeanStd` with clipping. Drop its torch dependency for
  numpy (the plant is numpy; SB3 handles its own tensors).
- **`seqrl/analysis/aggregate.py` → `btms/analysis/aggregate.py`.** Already walks
  an `outputs/` tree, groups runs by true `.hydra/config.yaml` (not directory
  name) across seeds, emits summary CSV + LaTeX table (mean ± std) + learning
  curves with std bands. **Change the grouping key from `(agent, pomdp, L)` to
  `(algo, scenario)`.** This closes the single-seed rigor gap for free.
- **`seqrl/configs/config.yaml`** — same Hydra shape: config groups under
  `defaults:`, `hydra.job.chdir: true`, run dir
  `outputs/${run_name}/${timestamp}`, TensorBoard backend, `latest.pt` resume.
- **`seqrl/scripts/run_baseline.{ps1,sh}`** — same dual-shell launcher pattern.
- **`docs/ARCHITECTURE.md`** — same "30-second mental model" + "read the code in
  this order" structure. Match the docstring style: explain **why**, not what.
  These files double as viva preparation.

---

## 7. Target layout

```
D:\Coding\RL-BTMS\
  btms/
    configs/     config.yaml + agent/{sac,td3,ppo}.yaml
                 + scenario/{mild,hot,fastcharge,mixed}.yaml
    plant/       vehicle.py  battery_electrical.py  battery_thermal.py
                 cooling.py  aging.py  pack.py  drive_cycles.py
    envs/        btms_env.py  wrappers.py  shield.py
    controllers/ base.py  null.py  bangbang.py  pid.py  mpc.py  tuning.py
    agents/      sb3_train.py
    analysis/    evaluate.py  aggregate.py  figures.py  deploy_bench.py
    utils/       normalizer.py  seeding.py
    train.py
  data/cycles/   real speed traces (csv)
  docs/ARCHITECTURE.md
  scripts/       run_all.ps1  run_all.sh
  outputs/       hydra run dirs
  report/results/ csv, latex, png
  tests/
  requirements.txt  README.md  .gitignore
```

---

## 8. Stages

### Stage 1 — skeleton
`git init` (**local only — no remote**). Create `.venv` on Python 3.13.
`requirements.txt`: torch (CPU index), `stable-baselines3>=2.4`, `gymnasium>=1.0`,
hydra-core, omegaconf, tensorboard, onnx, onnxruntime, numpy/scipy/matplotlib/pandas
— pinned, with the install route documented in comments (SAiDL style).
Port `normalizer.py`; write `utils/seeding.py`.

### Stage 2 — the plant

**`vehicle.py`** — longitudinal model, the step the old code skipped:
```
F = m·a + m·g·Cr·cosθ + ½·ρ·Cd·A·v² + m·g·sinθ
P_wheel = F·v ;  P_batt = P_wheel/η_dt (P>0) | P_wheel·η_regen (P<0)
I from P_batt = V·I with V = V_oc(SoC) − I·R   → quadratic solve
```
Mid-size EV: m ≈ 1800 kg, Cd ≈ 0.28, A ≈ 2.3 m², Cr ≈ 0.01, η ≈ 0.90,
60 kWh / ~350 V.

**`battery_electrical.py`** — OCV(SoC) lookup for NMC, R0(T), **one RC pair** for
realistic transients. Heat `Q = I²R0 + I²R1_transient`.

**`battery_thermal.py`** — **N = 4 nodes, not one:**
```
C_i·dT_i/dt = Q_gen,i − h_cool·A·(T_i − T_cool,i) − h_amb·A·(T_i − T_amb)
              + Σ_j k_ij·(T_j − T_i)
T_cool,i+1 = T_cool,i + Q_absorbed,i / (ṁ·cp)
```
Coolant **warms as it flows**, so downstream modules cool less than upstream.
Spatial ΔT now emerges from physics instead of being asserted, and pump speed
gains a real role (higher ṁ → smaller spread, at cubic power cost).

**`cooling.py`** — three actuators with distinct regimes:

| Actuator | Power | Sets | Effective when |
|---|---|---|---|
| pump `u_p` | `k_p·u_p³` (affinity law) | coolant ṁ | always |
| fan `u_f` | `k_f·u_f³` | radiator effectiveness → `T_cool_in → T_amb` | `T_cool > T_amb` |
| valve `u_v` | `Q_removed / COP`, COP ≈ 2.5 | chiller → `T_cool_in` **below** `T_amb` | any ambient |

*The fan being useless once coolant reaches ambient is exactly the mode decision a
fixed-gain loop cannot express. **This is the structural reason RL can win** — do
not collapse these back into one scalar.*

**`aging.py`** — Arrhenius severity vs a 25 °C reference,
`k(T) = A·exp(−Ea/(R·T))`, scaled by |C-rate|. **Highest-leverage single change:**
once running hot costs battery life, "never cool" stops being optimal and the
energy/longevity trade-off becomes real instead of degenerate.

**`pack.py`** — composes the above behind `step(current, action) -> state`; the one
seam shared by every controller and by the MPC.

**Validation before Stage 3:** OCV/R against a published NMC cell (or one *offline*
PyBaMM cross-check — **never inside the training loop**, far too slow); thermal
time constant within published range; energy-conservation residual ≈ 0.

### Stage 3 — real drive cycles
Load **real speed-vs-time traces**: UDDS/FTP-75, HWFET, US06 (EPA dynamometer
schedules), NEDC (UNECE) → `data/cycles/*.csv`, then through `vehicle.py`.
Record provenance per cycle. If a fetch fails, keep a synthetic surrogate but emit
a loud warning and mark provenance `synthetic`.

**Sanity gate (evidence-based clarification, 2026-09-21):** compare each raw-cycle
consumption against measured cycle references and verify units/energy accounting.
The original blanket 15-20 kWh/100 km range is not valid for all raw cycles:
DOE VTO 2020 EEMS Table II.1.3.2 reports Bolt UDDS/HWFET/US06/NEDC measurements
of approximately 11.41/12.57/17.70/12.20 kWh/100 km. Do not scale traces to force
an arbitrary range. Record vehicle differences and distinguish terminal demand,
internal losses, BTMS energy, and adjusted retail-label consumption.
Source: https://www.energy.gov/sites/default/files/2021-07/VTO_2020_APR_EEMS_06172021_compliant_.pdf


### Stage 4 — environment + the hardness gate

**`btms_env.py`** — `gymnasium.Env`, continuous `Box(3)` action (pump, fan, valve).
State: per-node temps (or max/mean/spread), SoC, C-rate, ambient, drive/charge
mode, plus an optional **preview** of demanded power over the next 30–60 s
(config flag — PID structurally cannot use it, making this the cleanest test of
the "anticipate, don't react" claim).

Reward — **normalise each term to O(1) before weighting:**
```
r = −( w_safe·band_violation + w_grad·ΔT_spatial
       + w_energy·P_aux·dt + w_age·aging_rate )
```

**`shield.py`** — supervisory override forcing full cooling above ~42 °C. Gives
zero violations *by construction*, adds **shield-firing rate** as a real policy
metric, and answers the existing viva question on hard constraints vs weighted sums.

**`wrappers.py`** — DQN action discretiser, obs normalisation via the ported
`RunningMeanStd`, preview assembly.

> ### 🚦 GATE — do not proceed past this line
> Run the **null controller** (cooling off) on `hot` and `fastcharge`. It **must
> violate the safe band.** If it does not, harden the scenarios — ambient 35–45 °C,
> 2–3C DC fast charge, graded US06 — and retest. Every result from Stage 5 onward
> is meaningless until this passes. **This is the defect that produced the 95%
> artifact.**

### Stage 5 — baselines worth beating
`controllers/base.py` defines one `act(obs) -> action` protocol; all controllers
and agents are interchangeable behind it.

- **`null.py`** — proves the problem is non-trivial; powers the gate.
- **`bangbang.py`** — honest industrial baseline: full cooling above `T_high`, off
  below `T_low`.
- **`pid.py` + `tuning.py`** — **the fairness fix.** Sweep set-point *and* gains
  against the **same objective the agent optimises**; use the winner. If a fairly
  tuned PID closes most of the gap, **that is a real finding — report it.**
- **`mpc.py`** — random-shooting / coarse-grid MPC over a short horizon using
  `pack.py` directly. **No CasADi/acados** — sampling keeps it ~60 lines and
  dependency-free. Gives the near-optimal upper bound *and* the solve-time figure
  Stage 7 needs.

`analysis/evaluate.py` generates the **fixed evaluation episode set** once —
`(cycle, ambient, initial SoC, seed)` tuples — replayed identically by every
controller. Structurally enforced, not merely claimed.

### Stage 6 — agents
**SAC** and **PPO** on the continuous 3-D action space; **DQN** on the discretised
wrapper for continuity with Phase-II. **Drop DDPG** — dominated by SAC, costs
training time, adds nothing.

- **5 seeds per algorithm** at a reduced step budget, not 1 seed at a large one.
- `device="cpu"`, `SubprocVecEnv` with 8–10 workers locally.
- TensorBoard scalar names must match what the adapted `aggregate.py` reads.
- Cite Agarwal et al., *Deep RL at the Edge of the Statistical Precipice*, for the
  reporting protocol.

**Metrics** (all on the fixed eval set): % time outside band · **true spatial
ΔT_max across nodes** · auxiliary energy Wh · aging severity · shield-firing rate.

**Generalization test:** train on 3 cycles, evaluate on the held-out 4th plus an
ambient outside the training range.

### Stage 7 — SDV deployment study — *the novelty*
`analysis/deploy_bench.py`, **CPU only** (there is no GPU in a car):

- Inference latency per control step: PyTorch → ONNX Runtime → int8 dynamic
  quantisation.
- **Headroom ratio** against a 10 Hz control period — the crux of deployability.
- Policy footprint in KB vs an equivalent gain table → the OTA payload argument.
- **Side by side against MPC solve time.** This is the money shot: near-equal
  control quality at ~2 orders of magnitude cheaper inference — precisely the gap
  Phase-I claims and no cited paper closes.

Optional: containerised cold-start, mirroring Wen et al. (ref [6]).

### Stage 8 — figures, report, deck
`analysis/figures.py` → training curves (mean ± std bands), temperature traces with
the safe band shaded, spatial-ΔT and energy comparison bars, latency table → into
`report/results/`.

Then: rewrite **Phase-III §3–4** and the **Mid-Term results** with honest numbers —
retire the `max |dT/dt|` "gradient proxy" language in favour of true spatial ΔT,
and correct the Phase-III design-review row claiming the reward was "implemented
as designed". Refresh the deck from copies of the Codex-built `.pptx` files.

---

## 9. Verification

| # | Check | Pass condition |
|---|---|---|
| 1 | `python -c "import torch, stable_baselines3, gymnasium"` | no error |
| 2 | `pytest tests/test_plant.py` | energy residual ≈ 0; T rises under load, falls at `u=1`; SoC monotone in discharge |
| 3 | `python -m btms.plant.drive_cycles --report` | 4 cycles load; 15–20 kWh/100 km; provenance `real` |
| 4 | `python -m btms.analysis.evaluate controller=null scenario=hot` | **band violated** (gate) |
| 5 | `python -m btms.analysis.evaluate controller=null scenario=mild` | shield never fires |
| 6 | `python -m btms.analysis.evaluate controller=pid --tune` | sweep selects a set-point; report it |
| 7 | `python -m btms.train agent=sac scenario=mixed seed=0` (short) | reward improves; TB scalars written |
| 8 | `scripts/run_all.ps1` | 3 algos × 5 seeds + 4 baselines complete |
| 9 | `python -m btms.analysis.aggregate --root outputs --out report/results` | CSV + LaTeX + curves, mean ± std |
| 10 | `python -m btms.analysis.deploy_bench` | latency/footprint table incl. MPC solve time, CPU model recorded |
| 11 | End-to-end read-through | every number in the updated report traceable to a file in `report/results/` |

---

## 10. The result to expect

On `hot` and `fastcharge`, RL should beat a **fairly tuned** PID on combined
energy + aging at equal safety, primarily by coordinating fan vs chiller across
ambient regimes. Expect **15–40%**, consistent with the literature — **not 95%**.

**A smaller honest number is a far stronger position in a viva than a large one
nobody believes.** If the fair PID turns out to be close, say so and pivot the
headline to multi-actuator coordination, preview, and the deployment-cost result —
which is the project's actual contribution anyway.

---

## 11. Boundaries

- Repo is **local git only** — do not add a remote or push without asking.
- The `.pptx` files under `C:\Users\parma\Documents\Codex\...` are build outputs:
  copy before editing.
- `D:\Claude Vault\Future-Ideas\` is off-limits entirely.
- Do not weaken the Stage 4 gate, re-collapse the action space to a scalar, or
  restore a single-node thermal model. Those three things *are* the rebuild.
