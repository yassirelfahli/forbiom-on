# Appendix — Repository guide

This appendix accompanies the FORBIOM-ON preliminary results report. The full shareable package lives in the public GitHub repository linked from the report’s Supplementary materials section.

## A.1 What is included

1. **Report** — DOCX and PDF of the preliminary results (cover placeholders, data/ABM methods, GAMS results).
2. **GAMS models** — `SA15.gms` (run underlying Section 7 tables) and `FORBIOM_ON.gms` (main NLP), plus eFAR→FORBIOM bridge scripts.
3. **Agent-based model** — Python source (`abm.py`, `calibrate.py`, `experiments.py`, …), calibration CSVs, and summary result tables for strategies S0–S6.
4. **Processing & mapping scripts** — FRI pipeline (`process_fri_data.py`), report builder, and map/heatmap utilities.
5. **Derived data** — CSV/TXT summaries of harvest, demand, and sensitivity runs (large FRI geodatabases and GDX binaries are omitted).
6. **Figures** — PNGs embedded in the report.
7. **Extended ABM docs** — Activity 3 simulation report and detailed-results appendix (DOCX).

## A.2 What is not redistributed

- Raw ARWoodS / eFAR extracts (Ontario MNR); only derived calibration tables are shared.
- FRI FIM v2 geodatabases and large `*.gpkg` / `*.gdx` binaries.
- Personal or administrative files unrelated to the models.

## A.3 How to reproduce key artefacts

| Artefact | Command / file |
|----------|----------------|
| GAMS counterfactual tables | Run `gams/SA15.gms` |
| ABM calibration tables | `python abm/calibrate.py` (needs raw extracts locally) |
| ABM experiments | `python abm/experiments.py` |
| Report DOCX | `python scripts/build_forbiom_report_docx.py` |

## A.4 Contact

For collaboration on FORBIOM-ON / FORBIOM-ABM, contact the report authors (Rasoul Yousefpour, Yasser Elfahli).
