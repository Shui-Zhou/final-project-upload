"""Tests for D1 published-station proximity artefacts."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PUBLISHED_PATH = (
    PROJECT_ROOT / "data" / "processed" / "lfb_published_station_locations_2026.parquet"
)
COMPARISON_PATH = (
    PROJECT_ROOT / "data" / "processed" / "lfb_station_d1_comparison_2024_2026.parquet"
)
BOROUGH_PROXIMITY_PATH = (
    PROJECT_ROOT / "data" / "processed" / "lfb_borough_station_proximity_2024_2026.parquet"
)


@pytest.fixture(scope="module")
def published() -> pd.DataFrame:
    if not PUBLISHED_PATH.exists():
        pytest.skip(
            f"published station parquet missing at {PUBLISHED_PATH}; "
            "run `python src/data/build_published_station_proximity.py` first"
        )
    return pd.read_parquet(PUBLISHED_PATH)


@pytest.fixture(scope="module")
def comparison() -> pd.DataFrame:
    if not COMPARISON_PATH.exists():
        pytest.skip(
            f"D1 comparison parquet missing at {COMPARISON_PATH}; "
            "run `python src/data/build_published_station_proximity.py` first"
        )
    return pd.read_parquet(COMPARISON_PATH)


@pytest.fixture(scope="module")
def borough_proximity() -> pd.DataFrame:
    if not BOROUGH_PROXIMITY_PATH.exists():
        pytest.skip(
            f"borough proximity parquet missing at {BOROUGH_PROXIMITY_PATH}; "
            "run `python src/data/build_published_station_proximity.py` first"
        )
    return pd.read_parquet(BOROUGH_PROXIMITY_PATH)


def test_published_station_rows_and_geocoding(published: pd.DataFrame) -> None:
    assert len(published) == 104
    assert published["station_name"].nunique() == 104
    assert published["postcode_geocoded"].notna().all()
    assert published["easting_m"].between(500_000, 565_000).all()
    assert published["northing_m"].between(155_000, 210_000).all()


def test_known_source_typos_are_corrected(published: pd.DataFrame) -> None:
    by_station = published.set_index("station_name")
    assert by_station.loc["Chelsea", "postcode_geocoded"] == "SW3 5UF"
    assert by_station.loc["Deptford", "postcode_geocoded"] == "SE8 5DB"
    assert by_station.loc["Lambeth", "postcode_geocoded"] == "SE1 7SP"
    assert "Eltham" in set(published["station_name"])
    assert "Hornchurch" in set(published["station_name"])
    assert "Northolt" in set(published["station_name"])


def test_d1_comparison_matches_existing_footprint_names(
    comparison: pd.DataFrame,
) -> None:
    assert len(comparison) == 104
    assert int(comparison["matched_to_derived_footprint"].sum()) == 102
    unmatched = set(
        comparison.loc[
            ~comparison["matched_to_derived_footprint"], "station_name_published"
        ]
    )
    assert unmatched == {"Lambeth River", "Merton"}
    matched = comparison[comparison["matched_to_derived_footprint"]]
    assert matched["published_vs_derived_distance_km"].notna().all()
    assert (matched["published_vs_derived_distance_km"] >= 0).all()


def test_borough_proximity_is_complete_and_nonnegative(
    borough_proximity: pd.DataFrame,
) -> None:
    assert len(borough_proximity) == 33
    assert borough_proximity["borough_canonical"].is_unique
    assert borough_proximity["nearest_station_name"].notna().all()
    assert (borough_proximity["nearest_station_distance_km"] >= 0).all()
