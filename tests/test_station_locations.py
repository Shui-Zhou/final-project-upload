"""
Tests for the derived station-location proxy
(`src/data/build_station_locations.py`).

Coverage extends the data-pipeline harness with the artefact that
`§5.5` (Station-Coverage Proxy) reads.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
STATION_LOCATIONS_PATH = (
    PROJECT_ROOT / "data" / "processed" / "lfb_station_locations_2024_2026.parquet"
)
CANONICAL_PATH = (
    PROJECT_ROOT / "data" / "processed" / "lfb_canonical_2024_2026.parquet"
)


@pytest.fixture(scope="module")
def stations() -> pd.DataFrame:
    if not STATION_LOCATIONS_PATH.exists():
        pytest.skip(
            f"station locations parquet missing at {STATION_LOCATIONS_PATH}; "
            "run `python src/data/build_station_locations.py` first"
        )
    return pd.read_parquet(STATION_LOCATIONS_PATH)


@pytest.fixture(scope="module")
def canonical() -> pd.DataFrame:
    if not CANONICAL_PATH.exists():
        pytest.skip(f"canonical missing at {CANONICAL_PATH}")
    return pd.read_parquet(CANONICAL_PATH)


def test_station_count_matches_canonical_unique(
    stations: pd.DataFrame, canonical: pd.DataFrame
) -> None:
    expected = canonical["IncidentStationGround"].dropna().nunique()
    assert len(stations) == expected, (
        f"station_locations has {len(stations)} rows but canonical has "
        f"{expected} unique IncidentStationGround values"
    )


def test_required_columns_present(stations: pd.DataFrame) -> None:
    required = {
        "station_name",
        "incident_count",
        "easting_centroid_m",
        "northing_centroid_m",
        "easting_iqr_m",
        "northing_iqr_m",
        "longitude",
        "latitude",
    }
    missing = required - set(stations.columns)
    assert not missing, f"missing required columns: {sorted(missing)}"


def test_station_names_unique(stations: pd.DataFrame) -> None:
    assert stations["station_name"].is_unique


def test_known_central_london_stations_are_central(stations: pd.DataFrame) -> None:
    """
    Spatial sanity: a handful of well-known central London stations should
    lie within the inner-London latitude band (north of 51.48 and south of
    51.55) and the central longitude band ([-0.25, 0.05]).
    """
    central_set = {"Soho", "Paddington", "Lambeth", "Euston"}
    found = stations[stations["station_name"].isin(central_set)]
    assert len(found) == len(central_set), (
        f"expected all of {central_set} present; found {set(found['station_name'])}"
    )
    for _, row in found.iterrows():
        assert 51.48 <= row["latitude"] <= 51.55, (
            f"{row['station_name']} latitude {row['latitude']} outside "
            "inner-London band"
        )
        assert -0.25 <= row["longitude"] <= 0.05, (
            f"{row['station_name']} longitude {row['longitude']} outside "
            "central London band"
        )


def test_centroids_inside_greater_london_bbox(stations: pd.DataFrame) -> None:
    assert stations["easting_centroid_m"].between(500_000, 565_000).all()
    assert stations["northing_centroid_m"].between(155_000, 210_000).all()


def test_wgs84_in_london_envelope(stations: pd.DataFrame) -> None:
    assert stations["longitude"].between(-0.6, 0.4).all()
    assert stations["latitude"].between(51.2, 51.8).all()


def test_iqr_columns_are_nonnegative(stations: pd.DataFrame) -> None:
    assert (stations["easting_iqr_m"] >= 0).all()
    assert (stations["northing_iqr_m"] >= 0).all()


def test_incident_counts_sum_close_to_canonical(
    stations: pd.DataFrame, canonical: pd.DataFrame
) -> None:
    """
    The station incident_count sum should equal the number of canonical rows
    with a non-null IncidentStationGround. The 2024-2026 slice has exactly
    one row missing IncidentStationGround.
    """
    expected = int(canonical["IncidentStationGround"].notna().sum())
    actual = int(stations["incident_count"].sum())
    assert actual == expected, (
        f"station counts sum {actual:,} != canonical non-null station rows "
        f"{expected:,}"
    )


def test_no_centroid_outside_canonical_bbox_per_station(
    stations: pd.DataFrame, canonical: pd.DataFrame
) -> None:
    """
    Per-station consistency: each station's centroid should be inside the
    bounding box of its own incidents (a derivation correctness check rather
    than a sanity-band check).
    """
    grouped = canonical.dropna(subset=["IncidentStationGround"]).groupby(
        "IncidentStationGround"
    )
    for station_name, group in grouped:
        row = stations.loc[stations["station_name"] == station_name]
        assert len(row) == 1
        e_min, e_max = group["Easting_rounded"].min(), group["Easting_rounded"].max()
        n_min, n_max = group["Northing_rounded"].min(), group["Northing_rounded"].max()
        ec = float(row["easting_centroid_m"].iloc[0])
        nc = float(row["northing_centroid_m"].iloc[0])
        assert e_min <= ec <= e_max, (
            f"{station_name} easting centroid {ec} outside its incident bbox "
            f"[{e_min}, {e_max}]"
        )
        assert n_min <= nc <= n_max, (
            f"{station_name} northing centroid {nc} outside its incident bbox "
            f"[{n_min}, {n_max}]"
        )
