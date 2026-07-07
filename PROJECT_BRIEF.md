# Project Brief

> Updated: 2026-07-07
> Purpose: compact project scope and evidence boundary reference.

## Identity

- Project: Emergency Services Response Visual Analytics.
- Degree/module: KCL MSc Individual Project, `7CCSMPRJ`.
- Artefact: reproducible open-data pipeline, Flask API, D3 dashboard, final thesis.
- Current stage: final report submission cleanup and validation.

## Research Question

How can an uncertainty-aware visual analytics dashboard support structured inspection of London Fire Brigade incident demand and first-pump response performance using public open data?

Supporting questions:

1. Which boroughs, incident groups, and time periods show persistent incident demand or six-minute first-pump attendance exceedance patterns in the 2024--2026 LFB open-data slice?
2. How do mobilisation records, false-alarm workload, coordinate suppression, missing response times, and station-address evidence qualify the interpretation of those patterns?
3. To what extent do the linked dashboard and report evidence package help users make useful but qualified analytical judgements without overstating station coverage, routing, or relocation claims?

## Scope

- Data window: 2024-01-01 to 2026-02-27.
- Incident source: London Fire Brigade Incident Records.
- Mobilisation source: London Fire Brigade Mobilisation Records, merged across 2021--2024 and 2025-onwards releases, then filtered to the canonical incident window.
- Spatial layer: London borough boundaries plus incident-derived station/borough footprint anchors and public station-address postcode recovery.
- Technology: Python, pandas, parquet, Flask, D3, pytest, LaTeX.

## Evidence Boundaries

- No operational dispatch model.
- No station-relocation recommendation.
- No routing-grade station-distance or travel-time model.
- No predictive incident-count model.
- The station-context layer is an assignment-footprint and public-address proximity cue, not real station coverage.
- The participant evaluation is a small-scale formative interpretability check, not a statistically generalisable user study.

## Read Order

1. `RUNBOOK.md`
2. `DATA_DICTIONARY.md`
3. `docs/API_CONTRACT.md`
4. `report/Final Report Latex Template (Data Science)/Thesis.pdf`
