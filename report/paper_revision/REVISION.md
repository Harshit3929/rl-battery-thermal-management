# Corrected canonical research paper - 27 October 2026

The canonical English output is `output/pdf/IEEE_BTMS_Research_Paper_Formatted.pdf`.
It was rebuilt from maintained editable text, rather than extracting an older PDF.
The previous PDF is preserved at `tmp/pdfs/paper-backup-20261027.pdf`.

## Content and scientific reporting corrections

1. Included all seven controllers in the cost/safety scatter; its caption now
   correctly identifies both PID and bang-bang as zero-violation raw outcomes.
2. Rebuilt the hot trace using actual verified rollout samples and the implemented
   42 C supervisor threshold. The embedded chart and caption now agree.
3. Consistently described equal-weight episode percentages, not pooled fractions
   of all simulated seconds. Recorded values were not replaced or rescaled.
4. Corrected driving-demand energy scope: drivetrain/regen assumptions and
   accessories are included; pack-internal losses and BTMS power are excluded.
5. Printed the exact implemented grade trigonometry in the road-force equation.
6. Combined all energy-residual terms into one two-line equation with one number
   and declared joule units. The TD3 schematic now states terminal masking and
   target-action clipping; the PPO surrogate's maximization direction is explicit.
7. Used KiB for file sizes computed by dividing bytes by 1024.
8. Stated that action agreement is checked across three components at one initial
   hot-state observation and timing uses repeated warmed fixed-observation calls.
9. Disclosed MPC's access to the full latent simulator state, exact future demand,
   same-model prediction and constant-action candidate search.
10. Established a single maintained source and synchronized PDF/TeX/bibliography.
    Venue compliance and evaluator-facing public links remain external requirements
    because the user confirmed those have not yet been decided. The paper and
    submission notes disclose that status without invented URLs.

## Reference update

Fifteen references are numbered in first-citation order. The original algorithm
and model/methodology references remain; four verified 2025-2026 studies were
added. The literature search was updated on 27 October 2026 and is targeted,
not an exhaustive systematic review. Statements about the new studies are
qualitative and identify their different plants/objectives. Their reported
performance gains are not claimed as this project's measured results.

- Shin, Jeong and Kim, *Computers & Chemical Engineering*, 204, 109406 (2026):
  https://doi.org/10.1016/j.compchemeng.2025.109406
- Arjmandzadeh et al., *SAE International Journal of Electrified Vehicles*,
  14(3), 427-446 (2025): https://doi.org/10.4271/14-14-03-0022
- Guo et al., *Expert Systems with Applications*, 276, 127221 (2025):
  https://doi.org/10.1016/j.eswa.2025.127221
- Najmi et al., *Energy and AI*, 24, 100751 (2026):
  https://doi.org/10.1016/j.egyai.2026.100751

Publisher records and abstracts establish the cited scope. Najmi author details
were also checked against the coauthor institution's publication record. Five
existing journal DOI metadata responses were retained in the preceding audit;
PMLR, arXiv, EPA, NeurIPS and JMLR records support the other original entries.
Crossref rate-limited the attempted bulk refresh, so recent records were checked
against publisher/author-institution sources instead; no failed lookup was
represented as a successful metadata fetch.

## Rebuild and verification

Edit `deliverables/IEEE_BTMS_Manuscript.json`, then run:

```powershell
.venv\Scripts\python.exe -B scripts/build_research_paper.py
.venv\Scripts\python.exe -B scripts/check_research_paper.py
```

Result tables and six plots read retained CSV, JSON, actual TensorBoard events and
verified replay samples. No new training or scientific result manipulation was
performed. The machine report checks data rows, citation resolution/ordering,
equations, caption placement, encoding, margins and input/figure fingerprints.
Every final rendered page was visually inspected separately. The TeX output is
content-synchronized, but no TeX engine was installed for a separate compilation.

The original 288-case reproduction and test reports remain as historical evidence.
They are not relabeled as new retraining or physical battery tests. This remains
a simulation-only, negative-result benchmark with the previously stated limits.
