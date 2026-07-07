# Emergency Services Response Visual Analytics

MSc Individual Project, King's College London (`7CCSMPRJ`).
Supervisor: Dr Alfie Abdul-Rahman.

## Overview

This repository contains the source code, data-processing pipeline, dashboard implementation, tests, and LaTeX report source for an open-data visual analytics project using London Fire Brigade incident and mobilisation records.

The project builds a reproducible evidence pipeline and an interactive Flask/D3 dashboard for inspecting incident demand, six-minute first-pump attendance exceedance patterns, coordinate coverage, and bounded station-context evidence across London boroughs.

## Scope

- Data window: 2024-01-01 to 2026-02-27.
- Primary sources: London Fire Brigade Incident Records, London Fire Brigade Mobilisation Records, ONS borough boundaries, and public station-address/postcode data.
- Main artefacts: canonical incident table, borough-month summaries, matched mobilisation artefact, station assignment-footprint centroids, public-address station proximity comparison, Flask API, D3 dashboard, report figures, and evaluation summaries.
- Non-goals: operational dispatch support, routing-grade travel-time modelling, station-relocation recommendation, real-time monitoring, and predictive forecasting.

The station layer is an assignment-footprint and public-address proximity context layer. It should not be interpreted as operational station coverage.

## Repository Map

| Path | Purpose |
|---|---|
| `src/data/` | Data-build scripts for canonical incidents, summaries, mobilisations, station context, and report figures |
| `src/api/` | Flask API serving dashboard-ready aggregates and station-context endpoints |
| `src/dashboard/` | D3 dashboard HTML, JavaScript, and CSS |
| `tests/` | API, data-contract, dashboard-asset, and evaluation-support tests |
| `data/processed/` | Processed artefact sidecars and small derived outputs where committed |
| `docs/API_CONTRACT.md` | Dashboard API contract |
| `DATA_DICTIONARY.md` | Index of dictionaries, provenance files, and data-quality memos |
| `report/Final Report Latex Template (Data Science)/` | Final report LaTeX source and compiled PDF |
| `RUNBOOK.md` | Rebuild, dashboard, test, and report compilation commands |

Large raw data files and local session notes are excluded from version control.

## Validation

Core checks:

```bash
python src/data/build_report_evaluation_figures.py
python -m pytest tests/ -q
python -m compileall src
```

Report compilation:

```bash
cd "report/Final Report Latex Template (Data Science)"
pdflatex -interaction=nonstopmode Thesis.tex
bibtex Thesis
pdflatex -interaction=nonstopmode Thesis.tex
pdflatex -interaction=nonstopmode Thesis.tex
```

Dashboard run command:

```bash
flask --app src.api.app:create_app run --port 5057
```

Then open `http://127.0.0.1:5057/dashboard`.
