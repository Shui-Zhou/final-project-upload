# API Contract

> Updated: 2026-05-02
> Scope: Flask API consumed by the D3 dashboard. This contract documents current behaviour, not future intent.

## General Rules

- API responses expose aggregates or proxy artefacts only; the raw canonical incident table is not served.
- JSON must not contain `NaN`; missing numeric values are serialised as `null`.
- Unknown query parameters are rejected with HTTP 400 on filtering endpoints.
- Empty analytical results are valid HTTP 200 responses with `row_count: 0`.
- Endpoint names deliberately use `footprint`, not `coverage`, for station-related proxy artefacts.

## `GET /health`

Returns service metadata.

Response fields:

| Field | Type | Notes |
|---|---|---|
| `status` | string | `"ok"` when the app starts successfully |
| `backing_artefact` | string | borough-summary parquet filename |
| `boundary_artefact` | string | borough-boundary GeoJSON filename |
| `rows` | integer | number of borough-summary rows |
| `columns` | string[] | columns present in the borough-summary artefact |

## `GET /api/borough_summary`

Returns borough x month x incident-group aggregate rows from `lfb_borough_summary_2024_2026.parquet`.

Allowed query parameters, all optional and repeatable:

| Query key | Meaning |
|---|---|
| `borough_canonical` | borough / local-authority canonical name |
| `year_month` | month in `YYYY-MM` format |
| `IncidentGroup` | LFB incident group, e.g. `Fire`, `False Alarm`, `Special Service` |

Repeated values are treated as an OR / `IN` filter. Different keys are intersected.

Success response:

| Field | Type | Notes |
|---|---|---|
| `rows` | object[] | one object per matched aggregate row |
| `row_count` | integer | length of `rows` |
| `filters_applied` | object | only keys that were supplied by the caller |

Unknown query key response:

```json
{
  "error": "unknown filter keys",
  "unknown_keys": ["ward"],
  "allowed_keys": ["borough_canonical", "year_month", "IncidentGroup"]
}
```

Status code: `400`.

## `GET /api/borough_boundaries`

Returns the London borough boundary layer as GeoJSON.

Current expected shape:

| Field | Type | Notes |
|---|---|---|
| `type` | string | `FeatureCollection` |
| `features` | object[] | 33 London local-authority features |

Mimetype: `application/geo+json`.

## `GET /api/station_footprints`

Returns incident-derived station responsibility-footprint centroids from `lfb_station_locations_2024_2026.parquet`.

Response fields:

| Field | Type | Notes |
|---|---|---|
| `rows` | object[] | one row per station footprint |
| `row_count` | integer | current expected value: 102 |
| `disclaimer` | string | required proxy framing |

Each row must include at least:

| Field | Type |
|---|---|
| `station_name` | string |
| `longitude` | number or null |
| `latitude` | number or null |

Important: this endpoint does not return published fire-station building coordinates. It returns assignment-footprint centroids derived from incident records.

## `GET /api/footprint_scenario`

Returns the first-release station-removal scenario calculation. The endpoint is a footprint proxy, not a location-allocation optimiser.

Allowed query parameter:

| Query key | Meaning |
|---|---|
| `remove` | repeatable station name to remove from the open-footprint set |

Success response:

| Field | Type | Notes |
|---|---|---|
| `rows` | object[] | one row per borough / local-authority area |
| `row_count` | integer | current expected value: 33 |
| `stations_removed` | string[] | station names removed by the query |
| `stations_open_count` | integer | number of station footprints remaining |
| `disclaimer` | string | required proxy framing |

Each row must include at least:

| Field | Type |
|---|---|
| `borough_canonical` | string |
| `nearest_footprint_station_name` | string |
| `nearest_footprint_distance_m` | number or null |
| `nearest_footprint_distance_km` | number or null |

Unknown query keys return HTTP 400. Removing an unknown station should not silently change a valid station name; tests should document the current behaviour before changing it.

## Dashboard Routes

| Route | Purpose |
|---|---|
| `GET /` | serves `src/dashboard/index.html` |
| `GET /dashboard` | serves `src/dashboard/index.html` |
| `GET /dashboard/<asset>` | serves dashboard static assets |

## Required Test Coverage

Relevant tests live in `tests/test_api.py` and should cover:

- health metadata
- dashboard static routes
- borough-boundary GeoJSON shape
- borough-summary schema and filters
- unknown filter key rejection
- unknown value returns empty result, not error
- station-footprint disclaimer and row count
- footprint-scenario baseline and removal behaviour
