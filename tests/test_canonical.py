"""
External invariants for the canonical LFB processed dataset.

These tests are independent of the build script's own validation checks:
they assert the *published* numbers cited in the report (so any drift
from the prelim baseline is caught), the schema contract that
downstream code relies on, and a handful of internal-consistency
properties that are too detailed for the build's validation checks.
"""

from __future__ import annotations

import pandas as pd
import pytest


# ---------------------------------------------------------------------------
# Schema contract
# ---------------------------------------------------------------------------


REQUIRED_RAW_COLUMNS = {
    "DateOfCall",
    "TimeOfCall",
    "IncidentGroup",
    "StopCodeDescription",
    "IncGeo_BoroughName",
    "FirstPumpArriving_AttendanceTime",
    "NumPumpsAttending",
    "Easting_m",
    "Northing_m",
    "Easting_rounded",
    "Northing_rounded",
    "IncidentStationGround",
}

REQUIRED_DERIVED_COLUMNS = {
    "year_month",
    "day_of_week",
    "weekday_name",
    "is_weekend",
    "hour_of_day",
    "response_time_seconds",
    "response_time_minutes",
    "exceeds_six_min_target",
    "coord_precise_valid",
    "coord_rounded_valid",
    "borough_canonical",
}


def test_required_raw_columns_present(canonical: pd.DataFrame) -> None:
    missing = REQUIRED_RAW_COLUMNS - set(canonical.columns)
    assert not missing, f"raw columns missing from canonical: {sorted(missing)}"


def test_required_derived_columns_present(canonical: pd.DataFrame) -> None:
    missing = REQUIRED_DERIVED_COLUMNS - set(canonical.columns)
    assert not missing, f"derived columns missing from canonical: {sorted(missing)}"


def test_dateofcall_is_datetime(canonical: pd.DataFrame) -> None:
    assert pd.api.types.is_datetime64_any_dtype(canonical["DateOfCall"])


def test_response_time_units_are_seconds(canonical: pd.DataFrame) -> None:
    rt = canonical["response_time_seconds"].dropna()
    median_rt = float(rt.median())
    # If units were milliseconds the median would be 60_000+; if minutes it
    # would be ~5. Seconds gives a median in 200--500.
    assert 60 < median_rt < 1200, (
        f"median response_time_seconds={median_rt:.1f} outside the seconds-units band"
    )


def test_response_time_minutes_consistent_with_seconds(canonical: pd.DataFrame) -> None:
    paired = canonical[["response_time_seconds", "response_time_minutes"]].dropna()
    if paired.empty:
        pytest.skip("no recorded response times to compare")
    diff = (paired["response_time_seconds"] / 60.0 - paired["response_time_minutes"]).abs()
    assert diff.max() < 1e-6, "response_time_minutes is not seconds / 60"


# ---------------------------------------------------------------------------
# Published-baseline invariants (anchored to the 2024-2026 prelim slice)
# ---------------------------------------------------------------------------


def test_row_count_matches_prelim_baseline(canonical: pd.DataFrame) -> None:
    # The prelim cited 293,646 rows. Allow +/- 1% to absorb minor LFB
    # republication noise.
    expected = 293_646
    assert abs(len(canonical) - expected) / expected < 0.01, (
        f"row count {len(canonical):,} drifted >1% from prelim baseline {expected:,}"
    )


def test_date_range_within_2024_to_2026(canonical: pd.DataFrame) -> None:
    dmin = canonical["DateOfCall"].min()
    dmax = canonical["DateOfCall"].max()
    assert dmin >= pd.Timestamp("2024-01-01"), f"earliest DateOfCall {dmin} pre-2024"
    assert dmax <= pd.Timestamp("2026-03-01"), f"latest DateOfCall {dmax} post-Feb-2026"


def test_borough_count_is_33(canonical: pd.DataFrame) -> None:
    boroughs = canonical["borough_canonical"].dropna().unique()
    # Greater London has 32 boroughs + the City of London = 33 named units.
    # Some LFB releases also include "Outside London" as an outlier label
    # for a tiny number of incidents straddling the boundary; allow up to 35.
    assert 32 <= len(boroughs) <= 35, (
        f"borough_canonical has {len(boroughs)} unique values, expected 33"
    )


def test_incident_group_taxonomy(canonical: pd.DataFrame) -> None:
    groups = set(canonical["IncidentGroup"].dropna().unique())
    expected = {"Fire", "False Alarm", "Special Service"}
    assert groups == expected, f"unexpected IncidentGroup values: {groups - expected}"


def test_false_alarm_share_baseline(canonical: pd.DataFrame) -> None:
    fa_share = float(canonical["IncidentGroup"].eq("False Alarm").mean())
    # Prelim baseline: 46.5%. Allow +/- 5pp.
    assert 0.41 <= fa_share <= 0.52, f"False Alarm share {fa_share:.3f} drifted from 0.465 baseline"


def test_six_minute_exceedance_baseline(canonical: pd.DataFrame) -> None:
    rt_present = canonical["response_time_seconds"].notna()
    exceed = float(canonical.loc[rt_present, "exceeds_six_min_target"].mean())
    # Prelim baseline: 32.4%. Allow +/- 5pp.
    assert 0.27 <= exceed <= 0.38, f"6-min exceedance {exceed:.3f} drifted from 0.324 baseline"


# ---------------------------------------------------------------------------
# Coordinate-validity contract
# ---------------------------------------------------------------------------


def test_precise_coord_share_in_band(canonical: pd.DataFrame) -> None:
    share = float(canonical["coord_precise_valid"].mean())
    # Prelim baseline: 37.9%.
    assert 0.30 <= share <= 0.45, f"precise coord share {share:.3f} drifted from 0.379 baseline"


def test_rounded_coord_share_close_to_one(canonical: pd.DataFrame) -> None:
    share = float(canonical["coord_rounded_valid"].mean())
    assert share >= 0.99, f"rounded coord share {share:.3f} below 0.99 invariant"


def test_precise_coord_implies_rounded(canonical: pd.DataFrame) -> None:
    # Any record with a precise coordinate should also have a rounded
    # coordinate inside the bbox (the rounded family is at coarser
    # precision, so it can never be invalid where the precise is valid).
    precise = canonical["coord_precise_valid"]
    rounded = canonical["coord_rounded_valid"]
    counterexamples = (precise & ~rounded).sum()
    assert counterexamples == 0, (
        f"{counterexamples} records have valid precise coords but invalid rounded coords; "
        "bbox or pipeline bug"
    )
