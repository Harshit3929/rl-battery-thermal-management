# Implementation status

Last updated: 2026-10-27. This file records evidence, not projected results.

## Completed

- Initialized local Git and a Python 3.13.14 virtual environment.
- Ported SAiDL's Chan running normalizer to NumPy.
- Implemented longitudinal road load, regeneration, a first-order electrical
  model, four thermal nodes, serial coolant warming, finite coolant inventory,
  independent pump/fan/chiller commands, and relative aging exposure.
- Five initial physics/normalizer tests passed using the existing Python installation.
- Downloaded official EPA-hosted UDDS, HWFET, US06, ECE and EUDC sources.
  NEDC is assembled from ECE x4 and EUDC x1. Source and CSV hashes are retained.

## Completed study stages

- The unshielded null-controller hardness gate passed: mild remains safe without cooling, while hot and fast-charge violate the safe band. See `report/results/hardness_gate.json`.
- PID tuning selected a 39 C set-point with Kp 0.6, Ki 0 and Kd 0 on a disjoint tuning split. Fixed evaluation covers tuned PID, bang-bang, null, sampling MPC, PPO, SAC and TD3.
- PPO, SAC and TD3 each trained for 20,000 environment steps across five seeds; saved checkpoints, metadata and TensorBoard events are under `outputs/study_20000`.
- Fixed held-out evaluation records shielded and unshielded metrics separately in `report/results/policy_evaluations.json` and `policy_evaluation_summary.csv`.
- The CPU deployment benchmark and report figures are complete. Updated copies of the Phase-III report, Mid-Term report and final deck are in `deliverables/`.

## Dashboard and reproduction evidence (2026-10-27)

- Added the local Python-backed research dashboard: `python -m btms.dashboard`.
  Fresh rollouts use the existing BTMSEnv and saved actors, with paired episode
  conditions, explicit safety supervision, source/model hashes and downloads.
- All 15 Python tests passed, including evidence consistency, saved-policy replay,
  changed-artifact rejection and HTTP request boundaries. Actual output and source
  hashes are saved in `report/dashboard/test_report.json`.
- All 288 learned-policy/PID/null/bang-bang evaluation rollouts reproduced their
  saved metrics at the documented floating tolerance, requiring exact safety,
  intervention and duration seconds. `report/dashboard/reproduction.json` records
  every comparison. A separate MPC HWFET spot-check also matches; the full MPC
  evaluation suite was not rerun.
- Headless Edge exercised fresh paired simulation, downloads, study results,
  TensorBoard-derived curves, paper evidence and mobile layout. Report and actual
  screenshots are in `report/dashboard/`.
- Manuscript tables match episode-derived means; saved standard deviations also
  reproduce. Corrected equal-episode-weight percentage descriptions, included
  drivetrain-loss wording, and the trace generator's 42 C supervisor annotation.
  See `docs/PAPER_EVIDENCE_AUDIT.md` for the precise scope and limits.

## Remaining evidence limits

- The electrical lookup receives a reduced-model PyBaMM SPMe cross-check, but thermal conductances and pack hardware mass remain engineering assumptions.
- Road-load consumption is 13.26/13.30/18.74/13.99 kWh per 100 km on UDDS/HWFET/US06/NEDC respectively, before pack internal losses and BTMS power. The values are retained rather than rescaled to force a generic range.
- The present learned policies do not beat the fairly tuned PID on shielded mean cost and violate the band without supervision. Laptop latency does not certify an automotive ECU.
## Scientific interpretations

- A full-cooling supervisor cannot guarantee safety if thermal capacity is
  insufficient. Measure violations and intervention frequency separately.
- Sampling MPC supplies a comparator, not a certified optimal bound.
- Laptop latency establishes laptop headroom; it cannot certify an automotive ECU.
- Aging is a dimensionless relative exposure model, not predicted capacity loss.
- UDDS is not full FTP-75. The latter contains an additional soak and repeat.

## Environment issue

Default sandbox shell calls began failing at process creation after setup with
`setup refresh had errors`. Automatically reviewed elevated shell calls work.
No manual commit/push is performed; the user's hook owns that operation.
