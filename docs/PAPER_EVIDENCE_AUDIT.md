# Manuscript evidence audit

This audit concerns `deliverables/IEEE_BTMS_Manuscript.tex`. Its status is
machine-generated in `report/dashboard/evidence.json`; fresh test and reproduction
evidence are separate timestamped JSON reports in the same directory.

## Checked evidence

- All 14 controller/supervisor aggregate rows are recalculated from the original
  per-episode records. Eight mean metrics and their standard deviations per row
  are checked against `controller_comparison.csv`.
- Both seven-row manuscript result tables are checked against those recalculated
  values using their printed precision, including half-unit rounding tolerance.
- Every controller/seed/supervisor evaluation group is checked against the
  original fixed eight-episode manifest, with duplicates detected.
- All 15 training runs are inspected for readable checkpoint ZIP containers,
  actual TensorBoard eval/return events, and event-step/metadata agreement.
- Retained driving CSV and original EPA source-file SHA-256 hashes are checked
  against the saved provenance, without replacing any source files.
- Fresh replay comparison reports record exactly which saved outcomes were
  reproduced and any differences. They do not certify a new training experiment.

## Corrections made during dashboard work

1. The temperature-figure generator labeled the supervisor threshold at 43 C.
   `btms/envs/shield.py` actually uses 42 C. The figure generator now uses 42 C;
   the PNG has been regenerated from actual SAC/PID rollouts. It remains excluded
   from the main manuscript as originally submitted.
2. Some manuscript wording described episode-averaged percentages as fractions of
   all evaluated seconds. The text now states equal weighting of episode-level
   percentages. Original numbers are unchanged.
3. The road-demand energy paragraph said drivetrain losses were excluded. The
   vehicle model includes drivetrain/regen efficiency and accessory demand. The
   text now identifies pack-internal losses and BTMS power as the excluded terms.

## Executed reproduction (2026-10-27)

All 240 saved RL evaluation outcomes (three algorithms, five seeds, two supervisor
modes, eight episodes), plus 48 PID/null/bang-bang outcomes, reproduce their saved
metrics. Duration, violation seconds and intervention seconds match exactly;
floating metrics use relative tolerance 1e-6 and absolute tolerance 1e-6, with
exact differences preserved. A separate supervised MPC HWFET spot-check matches.
This does not establish a rerun of all 16 MPC outcomes or a new training study.

The final Python test command reports 15 passed. A headless Edge test exercises
fresh SAC/PID simulation, actual run export, recorded results, training evidence,
manuscript download and desktop/mobile layout, with screenshots retained.
The timestamped reports are the primary evidence, rather than this prose summary.

## Interpretation limits

The manuscript reports a simulation study, not physical experimental data. The
speed traces have retained external provenance; thermal parameters, cooling
hardware, ambient conditions, grades and charge protocol are engineering
assumptions. Model temperatures and aging exposure are calculated quantities.

Internal consistency, hashes, and successful replay provide concrete evidence
for the inspected results; they cannot prove that no artifact was fabricated
historically. Do not make that blanket claim. Do not extend the check to older
DOCX, PPTX or PDF versions, all prose numbers, external references or historical
training authenticity without performing those additional audits.

The current result remains that short-budget RL does not beat tuned PID on the
main shielded cost metric, and raw learned policies violate the band. Supervisor
enabled safety cannot be attributed solely to the learned actor. Laptop latency
does not establish execution on an automotive ECU.

## Corrected formatted PDF (27 October 2026)

The final English formatted PDF has now received a separate content/citation and
rendered review. Its maintained editable source generates both the PDF and TeX.
The scientific/reporting findings from the quick PDF audit were corrected; all
fourteen programmatic checks pass and all nine final rendered pages were visually
inspected. The fifteen-reference bibliography includes four verified 2025-2026
primary studies, while foundational papers remain. See
`report/paper_revision/REVISION.md`, `validation.json` and `visual_review.json`.
This new PDF review is separate from the automated result-table audit described
above. The user confirmed that venue and public links are not decided, so those
external submission requirements remain explicitly pending.
