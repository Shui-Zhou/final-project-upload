"""
External invariants for the LFB mobilisations parquet.

These tests sit alongside the build script's own validation checks
(`src/data/build_mobilisations.py`) and concentrate on the join contract
back to the canonical incident artefact, not on the build mechanics.

These tests do not introduce a station-coverage or dispatch-optimisation
claim; they verify only the mobilisation join and deployment-evidence contract.
"""

from __future__ import annotations

import pandas as pd
import pytest


# ---------------------------------------------------------------------------
# Schema contract
# ---------------------------------------------------------------------------

REQUIRED_RAW_COLUMNS = {
    "IncidentNumber",
    "ResourceMobilisationId",
    "Resource_Code",
    "PerformanceReporting",
    "DateAndTimeMobilised",
    "DateAndTimeArrived",
    "AttendanceTimeSeconds",
    "DeployedFromStation_Code",
    "DeployedFromStation_Name",
    "DeployedFromLocation",
    "PumpOrder",
    "BoroughName",
}

REQUIRED_DERIVED_COLUMNS = {
    "mobilised_at",
    "arrived_at",
    "attendance_time_seconds",
    "attendance_time_minutes",
    "is_first_arriving_pump",
    "is_first_ordered_pump",
    "exceeds_six_min_target",
    "borough_canonical",
    "year_month",
    "mobilised_hour",
    "matches_canonical_incident",
}


def test_required_raw_columns_present(mobilisations: pd.DataFrame) -> None:
    missing = REQUIRED_RAW_COLUMNS - set(mobilisations.columns)
    assert not missing, f"raw columns missing from mobilisations: {sorted(missing)}"


def test_required_derived_columns_present(mobilisations: pd.DataFrame) -> None:
    missing = REQUIRED_DERIVED_COLUMNS - set(mobilisations.columns)
    assert not missing, f"derived columns missing from mobilisations: {sorted(missing)}"


def test_mobilised_at_is_datetime(mobilisations: pd.DataFrame) -> None:
    assert pd.api.types.is_datetime64_any_dtype(mobilisations["mobilised_at"])


def test_attendance_time_minutes_consistent_with_seconds(
    mobilisations: pd.DataFrame,
) -> None:
    paired = mobilisations[
        ["attendance_time_seconds", "attendance_time_minutes"]
    ].dropna()
    if paired.empty:
        pytest.skip("no recorded attendance times to compare")
    diff = (
        paired["attendance_time_seconds"] / 60.0 - paired["attendance_time_minutes"]
    ).abs()
    assert diff.max() < 1e-6, "attendance_time_minutes is not seconds / 60"


# ---------------------------------------------------------------------------
# Date filter contract
# ---------------------------------------------------------------------------


def test_date_filter_within_canonical_window(
    mobilisations: pd.DataFrame, canonical: pd.DataFrame
) -> None:
    canonical_min = canonical["DateOfCall"].min()
    canonical_max = canonical["DateOfCall"].max()
    mob_min = mobilisations["mobilised_at"].min()
    mob_max = mobilisations["mobilised_at"].max()
    assert mob_min >= canonical_min, (
        f"earliest mobilisation {mob_min} predates canonical window start {canonical_min}"
    )
    assert mob_max < canonical_max + pd.Timedelta(days=1), (
        f"latest mobilisation {mob_max} extends past canonical window end {canonical_max}"
    )


def test_attendance_time_units_are_seconds(mobilisations: pd.DataFrame) -> None:
    rt = mobilisations["attendance_time_seconds"].dropna()
    median_rt = float(rt.median())
    # If units were ms the median would be ~300_000; if minutes it would be ~5.
    # Seconds gives a median in the 200--500s band.
    assert 60 < median_rt < 1500, (
        f"median attendance_time_seconds={median_rt:.1f} outside the seconds-units band"
    )


# ---------------------------------------------------------------------------
# Performance-flag invariants
# ---------------------------------------------------------------------------


def test_first_arriving_pump_is_boolean(mobilisations: pd.DataFrame) -> None:
    s = mobilisations["is_first_arriving_pump"]
    assert s.dtype == bool or pd.api.types.is_bool_dtype(s), (
        f"is_first_arriving_pump dtype={s.dtype} should be a boolean"
    )


def test_first_arriving_pump_share_in_band(mobilisations: pd.DataFrame) -> None:
    share = float(mobilisations["is_first_arriving_pump"].mean())
    # ~1 first-arriving row per incident, mean pumps ~1.5, so share ~ 0.6--0.8.
    assert 0.30 <= share <= 0.95, (
        f"is_first_arriving_pump share={share:.3f} outside sanity band 0.30--0.95"
    )


def test_one_first_arriving_pump_per_incident(mobilisations: pd.DataFrame) -> None:
    """Each incident should have at most one row flagged as first-arriving.

    Multiple-flag cases would mean PerformanceReporting='1' is duplicated and
    downstream dedup logic would need to choose between them.
    """
    flagged = mobilisations[mobilisations["is_first_arriving_pump"]]
    counts_per_incident = flagged.groupby("IncidentNumber").size()
    # Allow a small share to have >1 flag (rare but observed in the raw data).
    multi_share = float((counts_per_incident > 1).mean()) if len(counts_per_incident) else 0.0
    assert multi_share <= 0.01, (
        f"{multi_share*100:.2f}% of incidents have >1 first-arriving-pump rows; "
        "expected near-zero. Investigate PerformanceReporting parsing."
    )


# ---------------------------------------------------------------------------
# Join contract back to canonical
# ---------------------------------------------------------------------------


def test_mobilisation_to_canonical_join_share(
    mobilisations: pd.DataFrame, canonical: pd.DataFrame
) -> None:
    """Most mobilisation rows should have a matching canonical IncidentNumber.

    A drop here typically means the IncidentNumber format drifted between
    the two open-data releases (leading zeros, dashes).
    """
    canonical_inc = set(canonical["IncidentNumber"].astype("string").dropna().unique())
    mob_inc = mobilisations["IncidentNumber"].astype("string")
    match_share = float(mob_inc.isin(canonical_inc).mean())
    assert match_share >= 0.99, (
        f"mobilisation->canonical match share {match_share*100:.2f}% < 99%; "
        "join key may have drifted"
    )


def test_canonical_dispatched_incidents_have_first_arriving_row(
    mobilisations: pd.DataFrame, canonical: pd.DataFrame
) -> None:
    """Strict: every canonical incident with a recorded FirstPumpArriving_AttendanceTime
    should have at least one mobilisation row tagged is_first_arriving_pump."""
    dispatched = canonical[
        canonical["FirstPumpArriving_AttendanceTime"].notna()
    ]["IncidentNumber"].astype("string")
    fa = mobilisations[mobilisations["is_first_arriving_pump"]]
    fa_inc = set(fa["IncidentNumber"].astype("string").dropna().unique())
    coverage = float(dispatched.isin(fa_inc).mean())
    assert coverage >= 0.99, (
        f"only {coverage*100:.2f}% of dispatched canonical incidents have a "
        "first-arriving mobilisation row (target >=99%)"
    )


def test_first_pump_time_matches_canonical(
    mobilisations: pd.DataFrame, canonical: pd.DataFrame
) -> None:
    """For canonical incidents with FirstPumpArriving_AttendanceTime, the
    minimum attendance_time_seconds across is_first_arriving_pump rows in
    the mobilisation table should match the canonical value to the second.
    """
    fa = mobilisations.loc[
        mobilisations["is_first_arriving_pump"]
        & mobilisations["IncidentNumber"].notna()
        & mobilisations["attendance_time_seconds"].notna(),
        ["IncidentNumber", "attendance_time_seconds"],
    ].copy()
    fa["IncidentNumber"] = fa["IncidentNumber"].astype("string")
    grouped = fa.groupby("IncidentNumber")["attendance_time_seconds"].min()

    can_first = canonical[
        ["IncidentNumber", "FirstPumpArriving_AttendanceTime"]
    ].dropna(subset=["FirstPumpArriving_AttendanceTime"]).copy()
    can_first["IncidentNumber"] = can_first["IncidentNumber"].astype("string")

    merged = can_first.join(grouped.rename("mob_min"), on="IncidentNumber", how="inner")
    if merged.empty:
        pytest.skip("no overlapping incidents to cross-check first-pump time")
    diff = (
        merged["mob_min"] - merged["FirstPumpArriving_AttendanceTime"]
    ).abs()

    median_abs = float(diff.median())
    within_30s = float((diff <= 30).mean())
    assert median_abs <= 5.0, (
        f"median |mob_first_arriving - canonical_first_pump|={median_abs:.1f}s "
        "exceeds 5s; data-vintage drift between releases?"
    )
    assert within_30s >= 0.99, (
        f"only {within_30s*100:.2f}% of cross-checked incidents agree to within 30s; "
        "expected near-100% because both fields trace to the same operational system"
    )


# ---------------------------------------------------------------------------
# Borough + station sanity
# ---------------------------------------------------------------------------


def test_borough_canonical_count(mobilisations: pd.DataFrame) -> None:
    boroughs = mobilisations["borough_canonical"].dropna().unique()
    # Greater London = 32 boroughs + City of London = 33. The mobilisation
    # release also records cross-boundary mobilisations (LFB attending
    # incidents in adjoining authorities such as Buckinghamshire, Slough,
    # Surrey), so the unique-borough count can run a few above 33. The
    # canonical incident artefact does NOT include these by construction;
    # this divergence is expected and is one of the reasons the join coverage
    # is checked with strict (dispatched) and loose (all) floors separately.
    assert 32 <= len(boroughs) <= 40, (
        f"borough_canonical has {len(boroughs)} unique values, expected ~33--38"
    )


def test_deployed_from_station_populated(mobilisations: pd.DataFrame) -> None:
    nonnull = mobilisations["DeployedFromStation_Name"].notna().mean()
    assert nonnull >= 0.99, (
        f"DeployedFromStation_Name non-null share {nonnull*100:.2f}% < 99%"
    )


# ---------------------------------------------------------------------------
# matches_canonical_incident flag
# ---------------------------------------------------------------------------


def test_matches_canonical_incident_is_boolean(mobilisations: pd.DataFrame) -> None:
    s = mobilisations["matches_canonical_incident"]
    assert s.dtype == bool or pd.api.types.is_bool_dtype(s), (
        f"matches_canonical_incident dtype={s.dtype} should be boolean"
    )
    # No NaN tolerated -- the flag must be a deterministic partition.
    assert s.notna().all(), "matches_canonical_incident contains NaN"


def test_matches_canonical_incident_share_strict(mobilisations: pd.DataFrame) -> None:
    """Flag share should be >=99% (the strict mobilisation-side floor).

    The remaining <1% are cross-boundary mobilisations (Buckinghamshire,
    Slough, Surrey) and a handful of vintage-drift rows; both are expected.
    """
    share = float(mobilisations["matches_canonical_incident"].mean())
    assert share >= 0.99, (
        f"matches_canonical_incident share {share*100:.2f}% < 99% strict floor"
    )


def test_matches_canonical_incident_truth_table(
    mobilisations: pd.DataFrame, canonical: pd.DataFrame
) -> None:
    """flag=True iff IncidentNumber is in the canonical set, no exceptions."""
    canonical_set = set(
        canonical["IncidentNumber"].astype("string").dropna().unique()
    )
    inc_str = mobilisations["IncidentNumber"].astype("string")
    expected = inc_str.isin(canonical_set)
    actual = mobilisations["matches_canonical_incident"]
    mismatches = int((expected != actual).sum())
    assert mismatches == 0, (
        f"matches_canonical_incident disagrees with recomputed isin() on "
        f"{mismatches:,} rows; the flag is stale or the canonical set drifted"
    )


def test_unmatched_rows_are_cross_boundary_or_unmapped(
    mobilisations: pd.DataFrame,
) -> None:
    """Unmatched rows should mostly be either outside the 33 London boroughs
    (cross-boundary mobilisations) or have a missing borough_canonical. If a
    large block of unmatched rows is inside London with a known borough, the
    join key may have drifted and needs investigation."""
    unmatched = mobilisations[~mobilisations["matches_canonical_incident"]]
    if len(unmatched) == 0:
        pytest.skip("no unmatched rows to characterise")

    london_boroughs = {
        "Barking And Dagenham", "Barnet", "Bexley", "Brent", "Bromley",
        "Camden", "City Of London", "Croydon", "Ealing", "Enfield",
        "Greenwich", "Hackney", "Hammersmith And Fulham", "Haringey",
        "Harrow", "Havering", "Hillingdon", "Hounslow", "Islington",
        "Kensington And Chelsea", "Kingston Upon Thames", "Lambeth",
        "Lewisham", "Merton", "Newham", "Redbridge", "Richmond Upon Thames",
        "Southwark", "Sutton", "Tower Hamlets", "Waltham Forest",
        "Wandsworth", "Westminster",
    }
    unexplained = unmatched[
        unmatched["borough_canonical"].isin(london_boroughs)
    ]
    unexplained_share = len(unexplained) / len(unmatched)
    # Allow up to 50% inside-London-with-borough; the rest must be missing
    # borough_canonical or in an adjoining authority. If this share is high it
    # is informational, not necessarily wrong; the strict join-key contract is
    # already covered by test_matches_canonical_incident_truth_table.
    assert unexplained_share <= 0.50, (
        f"{unexplained_share*100:.1f}% of unmatched rows are inside the 33 "
        "London boroughs; suspected join-key drift or incident-record "
        "vintage skew"
    )
