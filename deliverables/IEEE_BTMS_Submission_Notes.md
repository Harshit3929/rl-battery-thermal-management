# Canonical English research paper

Use `output/pdf/IEEE_BTMS_Research_Paper_Formatted.pdf`, revised 27 October 2026.
It has nine pages, fifteen references, six figures, eleven tables and eleven
numbered equations. Other Final/Complete/IEEE-named PDFs and the Mandarin
translation are historical versions and have not been synchronized to this edit.

## Edit and rebuild

- Editable text: `deliverables/IEEE_BTMS_Manuscript.json`.
- Maintained renderer: `scripts/build_research_paper.py`.
- Synchronized TeX export: `deliverables/IEEE_BTMS_Manuscript.tex`.
- Verified bibliography: `deliverables/IEEE_BTMS_References.json`.

From the project root:

```powershell
.venv\Scripts\python.exe -B scripts/build_research_paper.py
.venv\Scripts\python.exe -B scripts/check_research_paper.py
```

Install the project requirements and `requirements-paper.txt`. The renderer uses
Windows Times New Roman fonts and regenerates tables/plots from recorded data.
It does not train a model or change study results. The TeX export shares the same
content and figures; it has not been separately compiled because no TeX engine
was installed. The actual ReportLab PDF received rendered page-by-page QA.

Do not maintain the paper using the old temporary PDF-extraction builder. The
pre-revision PDF is retained in `tmp/pdfs/paper-backup-20261027.pdf`.

## Citations

Fifteen references were checked against primary publication/DOI/source records,
with a targeted literature update on 27 October 2026. Four 2025-2026 studies were
added while foundational algorithm/model papers remain. Citation numbering follows
first appearance. The paper explicitly distinguishes other studies from this
benchmark and does not present their performance as its own. This is not an
exhaustive systematic review. See `report/paper_revision/REVISION.md` and the
bibliography registry for source links and the precise verification scope.

## External submission requirements

The user confirmed that venue and public repository/Drive/demo links are not yet
decided. This is an IEEE-style general manuscript, not a venue-certified template.
Check the chosen venue's page limit, font/template, anonymization, author contacts,
copyright, funding/conflicts and AI-assistance requirements once known. Author
order and affiliation remain as supplied; author approval is not inferred.

Supply the companion evidence ZIP with the paper. Its recorded viewer does not
execute Python remotely. No public link has been invented; check eventual shared
links while signed out before evaluator use.

## Claim boundaries

This is a simulation study with assumed thermal/cooling parameters and a selected-
point electrical cross-check. It does not demonstrate physical-pack validation,
independently safe RL, automotive ECU execution or RL superiority over tuned PID.
The 288-case reproduction re-evaluates saved actors; it is not independent retraining.
