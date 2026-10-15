# FORBIOM-ON

**Ontario Forest Biomass: Supply Chain Feasibility, Processing Optimization, and ABM-Integrated Biomass Utilization**

Preliminary results package for **FORBIOM-ON** (GAMS NLP) and **FORBIOM-ABM** (Python agent-based model), covering six Ontario forest management units: Trout Lake, Abitibi, Algoma, Kenora, Nipissing, and Algonquin.

**Authors:** Rasoul Yousefpour · Yasser Elfahli

---

## Repository contents

| Path | Description |
|------|-------------|
| [`report/`](report/) | Polished preliminary-results DOCX and PDF |
| [`gams/`](gams/) | FORBIOM-ON optimization model (`SA15.gms`, `FORBIOM_ON.gms`) and eFAR bridge scripts |
| [`abm/`](abm/) | FORBIOM-ABM simulation (`abm.py`), calibration, experiments, and summary tables |
| [`scripts/`](scripts/) | FRI processing, report builder, and mapping utilities |
| [`data/`](data/) | Model-ready CSV inputs and GAMS/ABM summary outputs |
| [`figures/`](figures/) | Figures used in the report |
| [`docs/`](docs/) | Appendix materials (ABM detailed results and simulation report) |

---

## Quick start

### Report

The finished report is in:

- [`report/FORBIOM-ON_Preliminary_Results_Report_v2.docx`](report/FORBIOM-ON_Preliminary_Results_Report_v2.docx)
- [`report/FORBIOM-ON_Preliminary_Results_Report.pdf`](report/FORBIOM-ON_Preliminary_Results_Report.pdf)

To regenerate the DOCX (requires Python 3.11+, `python-docx`, Pillow; Word optional for TOC update):

```bash
python scripts/build_forbiom_report_docx.py
```

> Note: the report builder currently expects some figure paths relative to the original project layout. Prefer the packaged DOCX/PDF in `report/` unless you adapt those paths.

### FORBIOM-ON (GAMS)

Open and run:

- `gams/SA15.gms` — sensitivity / preliminary counterfactual run used for Section 7 tables
- `gams/FORBIOM_ON.gms` — main optimization model

Requires [GAMS](https://www.gams.com/) with an NLP solver (e.g. CONOPT).

### FORBIOM-ABM (Python)

```bash
cd abm
python calibrate.py      # refresh calibration tables from ARWoodS / eFAR extracts (if raw extracts are available)
python experiments.py    # strategy comparison, regional tuning, sensitivity
python analysis.py       # aggregate scores / tables
python figures.py        # optional figures
```

Core modules:

- `abm.py` — agents, logistic decision rules, markets, investment
- `experiments.py` — strategies S0–S6, MCDA criteria and weights
- `calibrate.py` — ARWoodS / eFAR → `calibration/*.csv`

---

## Models at a glance

**FORBIOM-ON** maximizes net value (including carbon costs) over 2020–2030 for six FMUs and four products (lumber, pulpwood, CLT, glulam), subject to harvest, capacity, and logistics constraints.

**FORBIOM-ABM** simulates annual harvest and processing decisions (2026–2045) with FMU managers, contractors, incumbent mills, and entrant plants under strategies S0–S6, evaluated with multi-criteria weights (economic, community, climate).

The two models are currently soft-linked; a co-evolutionary coupling (harvest intensity / adoption ↔ shadow prices) is planned.

---

## Data notes

- ARWoodS and eFAR extracts used for ABM calibration are Ontario MNR products; only derived calibration tables are redistributed here.
- FRI geodatabases and large GDX binaries are **not** included (size / redistribution). Processing scripts and CSV summaries are provided instead.
- Stock units and a few logistics capacities in FORBIOM-ON remain provisional; see the report (Sections 5.5 and 6.10).

---

## Citation

If you use this material, please cite the preliminary results report:

> Yousefpour, R. & Elfahli, Y. (2026). *Ontario Forest Biomass: Supply Chain Feasibility, Processing Optimization, and ABM-Integrated Biomass Utilization* (FORBIOM-ON preliminary results).

---

## License

Code in this repository is provided for research and collaboration under the MIT License (see [`LICENSE`](LICENSE)). External data remain under their original providers’ terms (Ontario MNR, GeoHub, Plonski yield tables, etc.).
