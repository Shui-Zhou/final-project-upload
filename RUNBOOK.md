# Runbook

> Purpose: minimal commands for installing, rebuilding, testing, running, and validating the project.

## Environment

```bash
source .venv/bin/activate
```

The current workspace already has a project `.venv`. In a fresh checkout, create one first:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

The default dependency file covers the tests, Flask dashboard API, parquet / Excel IO, and the current `pyproj` coordinate-conversion scripts. Boundary-regeneration work may additionally need `geopandas` and `shapely`.

## Rebuild Data Artefacts

Run from the repository root:

```bash
python src/data/build_canonical.py
python src/data/build_borough_summary.py
python src/data/build_station_locations.py
python src/data/build_published_station_proximity.py
python src/data/build_borough_centroids.py
python src/data/build_mobilisations.py
```

Expected result: each script reports its validation checks passed and updates the corresponding sidecar dictionary / provenance / DQ memo in `data/processed/`.

## Test

```bash
python -m pytest tests/ -q
python -m compileall src
```

Current baseline: 77 pytest tests pass.

## Run Dashboard Locally

```bash
flask --app src.api.app:create_app run --debug --port 5057
```

Open:

```text
http://127.0.0.1:5057/dashboard
```

Useful API validation checks:

```bash
curl -s http://127.0.0.1:5057/health
curl -s "http://127.0.0.1:5057/api/borough_summary?borough_canonical=Hillingdon&year_month=2025-06"
curl -s http://127.0.0.1:5057/api/station_footprints
curl -s "http://127.0.0.1:5057/api/footprint_scenario?remove=Soho"
```

## Compile Final Report

```bash
cd "report/Final Report Latex Template (Data Science)"
pdflatex -interaction=nonstopmode Thesis.tex
bibtex Thesis
pdflatex -interaction=nonstopmode Thesis.tex
pdflatex -interaction=nonstopmode Thesis.tex
```

Expected result: `Thesis.pdf` compiles with no undefined citations.

## Five-Minute Health Check

```bash
git status --short
python -m pytest tests/ -q
python -m compileall src
```

## Failure Handling

If the same command fails twice during one task:

1. Stop editing.
2. Record the exact command and error.
3. State what changed since the last passing state.
4. Suggest the smallest next diagnostic step.
