"""
Tests for the Flask backend (src/api/app.py).

Coverage maps to the public API contract: routes return 200, payload schema
matches the borough-summary parquet columns, filters round-trip correctly,
unknown filter keys are rejected, and unknown values return empty results
rather than errors.

The Flask test client is used end-to-end; no actual TCP socket is opened.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BOROUGH_SUMMARY_PATH = (
    PROJECT_ROOT / "data" / "processed" / "lfb_borough_summary_2024_2026.parquet"
)
BOROUGH_BOUNDARIES_PATH = (
    PROJECT_ROOT / "data" / "processed" / "london_borough_boundaries.geojson"
)
STATION_LOCATIONS_PATH = (
    PROJECT_ROOT / "data" / "processed" / "lfb_station_locations_2024_2026.parquet"
)
BOROUGH_CENTROIDS_PATH = (
    PROJECT_ROOT / "data" / "processed" / "lfb_borough_centroids_2024_2026.parquet"
)


@pytest.fixture(scope="module")
def app():
    if not BOROUGH_SUMMARY_PATH.exists():
        pytest.skip(
            f"borough-summary parquet missing at {BOROUGH_SUMMARY_PATH}; "
            "run `python src/data/build_borough_summary.py` first"
        )
    if not BOROUGH_BOUNDARIES_PATH.exists():
        pytest.skip(
            f"borough-boundary GeoJSON missing at {BOROUGH_BOUNDARIES_PATH}; "
            "download the GLA London Borough layer first"
        )
    if not STATION_LOCATIONS_PATH.exists():
        pytest.skip(
            f"station-locations parquet missing at {STATION_LOCATIONS_PATH}; "
            "run `python src/data/build_station_locations.py` first"
        )
    if not BOROUGH_CENTROIDS_PATH.exists():
        pytest.skip(
            f"borough-centroids parquet missing at {BOROUGH_CENTROIDS_PATH}; "
            "run `python src/data/build_borough_centroids.py` first"
        )
    from src.api.app import create_app

    return create_app(BOROUGH_SUMMARY_PATH)


@pytest.fixture(scope="module")
def client(app):
    return app.test_client()


@pytest.fixture(scope="module")
def borough_summary_df():
    return pd.read_parquet(BOROUGH_SUMMARY_PATH)


def test_health_returns_200_with_metadata(client, borough_summary_df):
    resp = client.get("/health")
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["status"] == "ok"
    assert payload["rows"] == len(borough_summary_df)
    assert set(payload["columns"]) == set(borough_summary_df.columns)
    assert payload["boundary_artefact"] == BOROUGH_BOUNDARIES_PATH.name


def test_dashboard_entrypoint_returns_html(client):
    resp = client.get("/dashboard")
    assert resp.status_code == 200
    assert b"LFB Response Atlas" in resp.data
    assert b"/dashboard/dashboard.js" in resp.data


def test_dashboard_static_asset_returns_javascript(client):
    resp = client.get("/dashboard/dashboard.js")
    assert resp.status_code == 200
    assert b"/api/borough_summary" in resp.data


def test_borough_boundaries_returns_geojson(client):
    resp = client.get("/api/borough_boundaries")
    payload = resp.get_json()
    assert resp.status_code == 200
    assert payload["type"] == "FeatureCollection"
    assert len(payload["features"]) == 33


def test_borough_summary_returns_200_with_no_filters(client, borough_summary_df):
    resp = client.get("/api/borough_summary")
    assert resp.status_code == 200
    payload = resp.get_json()
    # No filters -> full dataset.
    assert payload["row_count"] == len(borough_summary_df)
    assert payload["filters_applied"] == {}


def test_payload_schema_matches_parquet_columns(client, borough_summary_df):
    resp = client.get("/api/borough_summary")
    payload = resp.get_json()
    # Schema check: every parquet column should appear in every row dict
    # (NaN values become null but the key must still be present).
    sample = payload["rows"][0]
    expected_cols = set(borough_summary_df.columns)
    actual_cols = set(sample.keys())
    assert expected_cols == actual_cols, (
        f"missing in API: {expected_cols - actual_cols}; "
        f"extra in API: {actual_cols - expected_cols}"
    )


def test_borough_filter_round_trips(client, borough_summary_df):
    target = "Hillingdon"
    resp = client.get(f"/api/borough_summary?borough_canonical={target}")
    payload = resp.get_json()
    assert resp.status_code == 200
    assert payload["filters_applied"] == {"borough_canonical": [target]}

    expected_rows = (borough_summary_df["borough_canonical"] == target).sum()
    assert payload["row_count"] == expected_rows
    assert all(row["borough_canonical"] == target for row in payload["rows"])


def test_year_month_filter_round_trips(client, borough_summary_df):
    target = "2025-06"
    resp = client.get(f"/api/borough_summary?year_month={target}")
    payload = resp.get_json()
    assert resp.status_code == 200

    expected_rows = (borough_summary_df["year_month"] == target).sum()
    assert payload["row_count"] == expected_rows
    assert all(row["year_month"] == target for row in payload["rows"])


def test_incident_group_filter_round_trips(client, borough_summary_df):
    target = "Fire"
    resp = client.get(f"/api/borough_summary?IncidentGroup={target}")
    payload = resp.get_json()
    assert resp.status_code == 200

    expected_rows = (borough_summary_df["IncidentGroup"] == target).sum()
    assert payload["row_count"] == expected_rows
    assert all(row["IncidentGroup"] == target for row in payload["rows"])


def test_combined_filters_intersect(client, borough_summary_df):
    resp = client.get(
        "/api/borough_summary?borough_canonical=Hillingdon"
        "&year_month=2025-06&IncidentGroup=Fire"
    )
    payload = resp.get_json()
    assert resp.status_code == 200

    expected_rows = (
        (borough_summary_df["borough_canonical"] == "Hillingdon")
        & (borough_summary_df["year_month"] == "2025-06")
        & (borough_summary_df["IncidentGroup"] == "Fire")
    ).sum()
    assert payload["row_count"] == expected_rows


def test_multivalue_filter_unions(client, borough_summary_df):
    # Repeated query keys should be treated as an OR / IN list.
    resp = client.get(
        "/api/borough_summary?borough_canonical=Hillingdon&borough_canonical=Bromley"
    )
    payload = resp.get_json()
    assert resp.status_code == 200

    expected_rows = (
        borough_summary_df["borough_canonical"].isin(["Hillingdon", "Bromley"]).sum()
    )
    assert payload["row_count"] == expected_rows


def test_unknown_filter_value_returns_empty_not_error(client):
    resp = client.get("/api/borough_summary?borough_canonical=Atlantis")
    payload = resp.get_json()
    assert resp.status_code == 200
    assert payload["row_count"] == 0
    assert payload["rows"] == []


def test_unknown_filter_key_returns_400(client):
    resp = client.get("/api/borough_summary?ward=Hillingdon")
    payload = resp.get_json()
    assert resp.status_code == 400
    assert "unknown_keys" in payload
    assert payload["unknown_keys"] == ["ward"]


def test_station_footprints_returns_102_with_disclaimer(client):
    resp = client.get("/api/station_footprints")
    payload = resp.get_json()
    assert resp.status_code == 200
    assert payload["row_count"] == 102
    assert "disclaimer" in payload
    assert "exploratory proxy" in payload["disclaimer"].lower()
    sample = payload["rows"][0]
    assert {"station_name", "longitude", "latitude"}.issubset(sample.keys())


def test_footprint_scenario_baseline_returns_33_boroughs(client):
    resp = client.get("/api/footprint_scenario")
    payload = resp.get_json()
    assert resp.status_code == 200
    assert payload["row_count"] == 33
    assert payload["stations_removed"] == []
    assert payload["stations_open_count"] == 102
    assert "disclaimer" in payload
    sample = payload["rows"][0]
    assert {
        "borough_canonical",
        "nearest_footprint_station_name",
        "nearest_footprint_distance_m",
        "nearest_footprint_distance_km",
    }.issubset(sample.keys())


def test_footprint_scenario_remove_increases_some_distances(client):
    """
    Removing a real station footprint should never *decrease* any borough's
    nearest-footprint distance versus baseline; for at least one borough the
    distance should strictly increase (the borough whose nearest open footprint
    was the removed one).
    """
    baseline = client.get("/api/footprint_scenario").get_json()
    baseline_by_borough = {
        r["borough_canonical"]: r["nearest_footprint_distance_m"]
        for r in baseline["rows"]
    }

    # Pick a real station footprint that is nearest for at least one borough --
    # use Soho (the busiest station, central London).
    scenario = client.get("/api/footprint_scenario?remove=Soho").get_json()
    scenario_by_borough = {
        r["borough_canonical"]: r["nearest_footprint_distance_m"]
        for r in scenario["rows"]
    }

    increased = 0
    for borough, dist in scenario_by_borough.items():
        assert dist >= baseline_by_borough[borough] - 1e-3, (
            f"{borough} distance decreased after removing a station footprint: "
            f"baseline {baseline_by_borough[borough]:.1f} m, "
            f"scenario {dist:.1f} m"
        )
        if dist > baseline_by_borough[borough] + 1e-3:
            increased += 1
    assert increased >= 1, (
        "removing Soho (busiest central-London station footprint) did not "
        "increase any borough's nearest-footprint distance; suspect footprint logic"
    )


def test_footprint_scenario_unknown_station_returns_400(client):
    resp = client.get("/api/footprint_scenario?remove=Atlantis")
    payload = resp.get_json()
    assert resp.status_code == 400
    assert "unknown_stations" in payload
    assert payload["unknown_stations"] == ["Atlantis"]


def test_footprint_scenario_unknown_query_key_returns_400(client):
    resp = client.get("/api/footprint_scenario?ward=Hillingdon")
    payload = resp.get_json()
    assert resp.status_code == 400
    assert payload["unknown_keys"] == ["ward"]


def test_footprint_scenario_remove_all_returns_400(client):
    """
    Removing every station footprint should be rejected, not silently return an
    empty nearest-footprint calculation that might be misread as "no assignment
    shift" rather than "invalid input".
    """
    # Use station_footprints to grab the full list rather than hard-code 102
    # names.
    stations_payload = client.get("/api/station_footprints").get_json()
    all_names = [r["station_name"] for r in stations_payload["rows"]]
    qs = "&".join(f"remove={n}" for n in all_names)
    resp = client.get(f"/api/footprint_scenario?{qs}")
    payload = resp.get_json()
    assert resp.status_code == 400
    assert "every station footprint removed" in payload["error"]


def test_payload_is_json_safe_no_nan(client):
    """
    pandas float NaN is not JSON-serialisable per RFC 8259. Verify that
    every numeric column survives serialisation and that NaN became
    JSON null in the payload, not the literal "NaN" string or a Python
    float.
    """
    resp = client.get("/api/borough_summary")
    payload = resp.get_json()
    # If json.loads worked, payload is fine; just spot-check there are no
    # string NaNs masquerading as numbers.
    for row in payload["rows"][:5]:
        for v in row.values():
            assert v != "NaN", "NaN was serialised as a string"
            if isinstance(v, float):
                assert v == v, "raw float NaN survived serialisation"  # NaN != NaN
