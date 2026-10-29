# Rebuilt Study Traceability Review

Date: 2026-09-21

This register links the final report, presentation, figures, and implementation-plan checks to the files that contain the recorded evidence. It distinguishes completed simulation evidence from claims that need measured hardware validation.

| Plan item | Evidence | Status and interpretation |
| --- | --- | --- |
| Dependency setup | `.venv` and `requirements.txt` | Complete. Import and test checks run in the project virtual environment. |
| Plant and environment checks | `tests/test_plant.py`, `tests/test_env.py` | Complete. Ten tests passed on 2026-09-21. Gymnasium warns that the observation space has infinite bounds. |
| Electrical reference check | `report/results/parameter_reference.json` | Complete as a reduced-model PyBaMM SPMe cross-check at four state-of-charge points. It does not validate a physical pack. |
| Real driving inputs | `data/cycles/*.csv`, `data/cycles/*.json`, `report/results/cycle_report.json` | Complete. UDDS, HWFET, US06, ECE and EUDC source provenance and hashes are recorded. NEDC is assembled from ECE x4 plus EUDC. |
| Consumption sanity review | `report/results/cycle_report.json`, `PLAN.md` Stage 3 clarification | Complete with an evidence-based deviation. The raw road-load values are 13.26, 13.30, 18.74 and 13.99 kWh per 100 km for UDDS, HWFET, US06 and NEDC. They were not rescaled to force a blanket 15-20 range. |
| Hardness gate | `report/results/hardness_gate.json` | Complete. Null cooling violates the hot band for 1,472/1,800 s and the fast-charge band for 1,181/1,350 s. Mild remains safe without cooling. |
| Fair PID baseline | `report/results/pid_tuning.json`, `report/results/pid_shielded_evaluation.json` | Complete. Tuning on the disjoint split selected 39 C, Kp 0.6, Ki 0 and Kd 0. |
| Learned-policy training | `outputs/study_20000/*/metadata.json`, checkpoints and TensorBoard event files | Complete. PPO, SAC and TD3 each ran for 20,000 steps across five seeds. |
| Fixed controller evaluation | `data/evaluation_episodes.json`, `report/results/policy_evaluations.json`, `report/results/policy_evaluation_summary.csv` | Complete. Every controller replays the same eight held-out episodes. Shielded and unshielded metrics remain separate. |
| Shielded conclusion | `report/results/policy_evaluation_summary.csv` | The shield records zero band violation for all evaluated controllers. PPO, SAC and TD3 fire it for 22.70%, 19.63% and 21.85% of steps. The tuned PID has lower shielded mean cost than each learned policy. |
| Unshielded conclusion | `report/results/policy_evaluation_summary.csv` | PPO, SAC and TD3 violate the band for 42.28%, 41.15% and 42.08% of evaluated time. The present policies are not independently safe. |
| Deployment benchmark | `report/results/deployment_benchmark_sac_seed0.json` | Complete on the recorded 13th Gen Intel Core i5-13420H laptop CPU. ONNX median latency is 0.0170 ms; sampling MPC median solve time is 228.9490 ms. This is not automotive-ECU certification. |
| Report figures | `report/results/curve_mixed.png`, `controller_comparison_shielded.png`, `safety_intervention_comparison.png`, `deployment_latency.png`, `temperature_trace_hot_s701.png` | Complete. `btms/analysis/figures.py` regenerates the new comparison, intervention, latency and fixed-trace figures without training. |
| Updated reports | `deliverables/Phase3_Report_RL_Battery_Thermal_Management_Rebuilt_Results.docx`, `deliverables/MidTerm_Evaluation_Report_Rebuilt_Results.docx` | Complete. The rebuilt sections retire the synthetic-cycle, tabular-Q-learning, 95% energy-saving, and temporal-gradient-proxy claims. |
| Updated presentation | `deliverables/RL_BTMS_Final_Presentation_Rebuilt_Results.pptx` | Complete. The copied deck states the rebuilt results, supervisory-safety dependence, and remaining validation work. |

## Final claim boundary

The project now demonstrates a reproducible simulation study with real-cycle provenance, a non-degenerate thermal-control gate, fairly tuned baselines, five-seed training, fixed evaluations, shield-intervention measurement, and a laptop deployment benchmark. It does not demonstrate that the present learned policies beat the tuned PID, that they are safe without supervision, or that the laptop measurements certify a vehicle ECU.

## Dashboard verification update (2026-10-27)

The local dashboard now runs the existing simulator and saved policies. All 288
non-MPC fixed evaluation rollouts reproduce the saved metrics under a documented
floating tolerance with exact safety/intervention/duration seconds. One separate
MPC HWFET rollout also matches. Fifteen Python tests and browser interaction/
mobile layout checks pass; timestamped outputs and screenshots are retained in
`report/dashboard/`. Manuscript table consistency is checked automatically.
See `docs/PAPER_EVIDENCE_AUDIT.md`; these checks do not certify historical
authenticity, physical validation, every prose claim or other document versions.

## Artifact QA limitation

The updated DOCX and PPTX packages were structurally inspected after writing. Full visual-render QA could not run in this workspace because the available document renderer stops on a missing `pdf2image` dependency and the required presentation artifact API package is absent. These files should be opened once in Word and PowerPoint before submission to inspect page and slide layout.
