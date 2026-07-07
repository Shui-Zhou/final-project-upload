# Data Dictionary Index

> Updated: 2026-07-06
> Purpose: compact index of data dictionaries, provenance files, and data-quality memos. Do not paste raw data here; use Python for tables and sidecars for schema/provenance.

## Canonical Incident Artefact

- Build script: `src/data/build_canonical.py`
- Binary output: `data/processed/lfb_canonical_2024_2026.parquet` (excluded from version control)
- Dictionary: `data/processed/lfb_canonical_2024_2026_dictionary.md`
- Data-quality memo: `data/processed/lfb_canonical_2024_2026_dq_memo.md`
- Provenance: `data/processed/lfb_canonical_2024_2026_provenance.json`
- Key rule: no rows dropped during canonicalisation; missingness is encoded with explicit flags.

## Borough Summary Artefact

- Build script: `src/data/build_borough_summary.py`
- Binary output: `data/processed/lfb_borough_summary_2024_2026.parquet` (excluded from version control)
- Dictionary: `data/processed/lfb_borough_summary_2024_2026_dictionary.md`
- Provenance: `data/processed/lfb_borough_summary_2024_2026_provenance.json`
- Key grain: borough x year-month x incident group.

## Mobilisation Artefact

- Build script: `src/data/build_mobilisations.py`
- Binary output: `data/processed/lfb_mobilisations_2024_2026.parquet` (excluded from version control)
- Dictionary: `data/processed/lfb_mobilisations_2024_2026_dictionary.md`
- Data-quality memo: `data/processed/lfb_mobilisations_2024_2026_dq_memo.md`
- Join-quality memo: `data/processed/lfb_mobilisations_2024_2026_join_quality_memo.md`
- Provenance: `data/processed/lfb_mobilisations_2024_2026_provenance.json`
- Join key: `IncidentNumber`.
- Critical flag: `matches_canonical_incident`.
- Rule for §6/dashboard claims: filter to `matches_canonical_incident == True` unless explicitly analysing cross-boundary/unmatched rows.

## Assignment-Footprint Artefacts

- Station-footprint script: `src/data/build_station_locations.py`
- Station-footprint dictionary: `data/processed/lfb_station_locations_2024_2026_dictionary.md`
- Station-footprint provenance: `data/processed/lfb_station_locations_2024_2026_provenance.json`
- Borough-centroid script: `src/data/build_borough_centroids.py`
- Borough-centroid dictionary: `data/processed/lfb_borough_centroids_2024_2026_dictionary.md`
- Borough-centroid provenance: `data/processed/lfb_borough_centroids_2024_2026_provenance.json`
- Key warning: these are incident-derived assignment footprints, not published station building coordinates.

## Published Station Proximity Artefacts (D1 Recovery)

- Build script: `src/data/build_published_station_proximity.py`
- Source page: London Datastore `Low Carbon Generators` LFEPA/LFB fire-station address table.
- Raw CSV: `data/raw/LFB_low_carbon_generators_at_fire_stations_June_2017.csv` (excluded from version control)
- Published-station binary output: `data/processed/lfb_published_station_locations_2026.parquet` (excluded from version control)
- Published-station dictionary: `data/processed/lfb_published_station_locations_2026_dictionary.md`
- Published-station DQ memo: `data/processed/lfb_published_station_locations_2026_dq_memo.md`
- Published-station provenance: `data/processed/lfb_published_station_locations_2026_provenance.json`
- Station D1 comparison: `data/processed/lfb_station_d1_comparison_2024_2026_dictionary.md`, `data/processed/lfb_station_d1_comparison_2024_2026_dq_memo.md`
- Borough proximity summary: `data/processed/lfb_borough_station_proximity_2024_2026_dictionary.md`, `data/processed/lfb_borough_station_proximity_2024_2026_dq_memo.md`
- Report figures: `report/Final Report Latex Template (Data Science)/figures/station_proximity/*.png`
- Key warning: these are public postcode-geocoded station-address coordinates for straight-line proximity/accessibility context only. They are not routing-grade coverage, dispatch, relocation, or optimisation evidence.

## Report Results / Evaluation Figures

- Build script: `src/data/build_report_evaluation_figures.py`
- Summary JSON: `data/processed/lfb_report_evaluation_figures_summary.json`
- Summary memo: `data/processed/lfb_report_evaluation_figures_memo.md`
- Per-figure memos: `data/processed/report_figure_*_memo.md`
- Report figures: `report/Final Report Latex Template (Data Science)/figures/early_context/*.png` and `report/Final Report Latex Template (Data Science)/figures/results_evaluation/*.png`
- Figure set: motivation borough exceedance map, coordinate-uncertainty implication diagram, linked-view wireframe, borough exceedance ranking, incident-group response distribution, precise-coordinate coverage by borough, hour-of-day × weekday incident-density heatmap, false-alarm sensitivity ranking, and precise-subset spatial-density hexbin.
- Key warning: the PNG/memo artefacts are system/data/design evaluation and robustness artefacts. Participant evaluation material is indexed separately under `tests/evaluation/`.

## Boundary Artefact

- Boundary GeoJSON: `data/processed/london_borough_boundaries.geojson`
- Provenance: `data/processed/london_borough_boundaries_provenance.json`
- Key grain: 33 London local-authority areas.

## Verification Commands

```bash
python src/data/build_canonical.py
python src/data/build_borough_summary.py
python src/data/build_station_locations.py
python src/data/build_published_station_proximity.py
python src/data/build_borough_centroids.py
python src/data/build_mobilisations.py
python -m pytest tests/ -q
```
