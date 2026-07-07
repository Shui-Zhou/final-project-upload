"""
External invariants for the borough x month x incident-group summary table.

These tests verify that the second-stage aggregation is internally
consistent with the canonical it was built from, and that the summary's
column contract matches what the dashboard backend (S5.3) is going to
rely on.
"""

from __future__ import annotations

import pandas as pd


REQUIRED_COLUMNS = {
    "borough_canonical",
    "year_month",
    "IncidentGroup",
    "incident_count",
    "response_time_min_mean",
    "response_time_min_median",
    "response_time_min_p90",
    "response_time_min_p95",
    "response_time_recorded_share",
    "exceeds_six_min_share",
    "num_pumps_mean",
    "coord_precise_share",
    "coord_rounded_share",
    "distinct_ground_stations",
}


def test_required_columns_present(borough_summary: pd.DataFrame) -> None:
    missing = REQUIRED_COLUMNS - set(borough_summary.columns)
    assert not missing, f"borough summary missing columns: {sorted(missing)}"


def test_group_keys_unique(borough_summary: pd.DataFrame) -> None:
    keys = borough_summary[["borough_canonical", "year_month", "IncidentGroup"]]
    assert not keys.duplicated().any(), "duplicate (borough, month, group) cells"


def test_cell_count_within_expected_grid(borough_summary: pd.DataFrame) -> None:
    # 33 boroughs * 26 months * 3 groups = 2574 maximal; observed should be
    # in 50-100% of that (some months x boroughs x groups have zero rows).
    n_rows = len(borough_summary)
    assert 1200 <= n_rows <= 2574, f"borough summary row count {n_rows} unexpected"


def test_incident_count_sums_match_canonical(
    borough_summary: pd.DataFrame, canonical: pd.DataFrame
) -> None:
    # The summary may drop a small number of rows for null IncidentGroup or
    # null borough_canonical; allow up to 1% drift.
    canonical_total = len(canonical)
    summary_total = int(borough_summary["incident_count"].sum())
    drift = abs(canonical_total - summary_total) / canonical_total
    assert drift < 0.01, (
        f"summary total {summary_total:,} differs from canonical {canonical_total:,} by >1%"
    )


def test_response_time_means_in_sanity_band(borough_summary: pd.DataFrame) -> None:
    rt = borough_summary["response_time_min_mean"].dropna()
    assert rt.min() >= 1.0, f"min cell mean {rt.min():.2f} < 1 min, suspect"
    assert rt.max() <= 30.0, f"max cell mean {rt.max():.2f} > 30 min, suspect"


def test_percentiles_are_ordered(borough_summary: pd.DataFrame) -> None:
    # Within a row, median <= p90 <= p95 should always hold.
    df = borough_summary.dropna(
        subset=[
            "response_time_min_median",
            "response_time_min_p90",
            "response_time_min_p95",
        ]
    )
    assert (df["response_time_min_median"] <= df["response_time_min_p90"]).all(), (
        "median > p90 in some cell"
    )
    assert (df["response_time_min_p90"] <= df["response_time_min_p95"]).all(), (
        "p90 > p95 in some cell"
    )


def test_share_columns_are_probabilities(borough_summary: pd.DataFrame) -> None:
    for col in [
        "response_time_recorded_share",
        "exceeds_six_min_share",
        "coord_precise_share",
        "coord_rounded_share",
    ]:
        s = borough_summary[col].dropna()
        assert s.min() >= 0.0 and s.max() <= 1.0, (
            f"{col} not in [0, 1]: min={s.min()}, max={s.max()}"
        )


def test_borough_set_matches_canonical(
    borough_summary: pd.DataFrame, canonical: pd.DataFrame
) -> None:
    # Every borough that has at least one incident in the canonical should
    # appear in the summary.
    canonical_boroughs = set(canonical["borough_canonical"].dropna().unique())
    summary_boroughs = set(borough_summary["borough_canonical"].dropna().unique())
    missing = canonical_boroughs - summary_boroughs
    assert not missing, f"boroughs in canonical but not in summary: {sorted(missing)}"


def test_exceeds_six_min_share_uses_recorded_time_denominator(
    borough_summary: pd.DataFrame, canonical: pd.DataFrame
) -> None:
    """Regression test for the recorded-time denominator.

    `exceeds_six_min_share` must be the share of cells *with a recorded
    first-pump time* that exceeded six minutes -- NOT the share of all
    incidents (which would silently treat missing-time rows as
    non-exceedances and deflate the value).

    We recompute the share from the canonical, filtered to rows with a
    non-null `response_time_seconds`, and assert it matches the summary
    cell-by-cell to within floating-point tolerance.
    """
    rt_present = canonical["response_time_seconds"].notna()
    canonical_rt = canonical.loc[rt_present].copy()

    expected = (
        canonical_rt.groupby(
            ["borough_canonical", "year_month", "IncidentGroup"], observed=True
        )["exceeds_six_min_target"]
        .mean()
        .reset_index(name="expected_share")
    )

    merged = borough_summary.merge(
        expected,
        on=["borough_canonical", "year_month", "IncidentGroup"],
        how="left",
    )

    # Cells where every incident lacks a recorded time produce no expected
    # share. Drop them; the summary value will already be NaN there.
    both_present = merged["expected_share"].notna() & merged["exceeds_six_min_share"].notna()
    diffs = (
        merged.loc[both_present, "exceeds_six_min_share"]
        - merged.loc[both_present, "expected_share"].astype(float)
    ).abs()

    # The summary parquet rounds float columns to 4 dp for readability
    # (see build_borough_summary.py); allow that rounding error plus a
    # small float-arithmetic margin. Anything bigger indicates a real
    # denominator regression.
    max_diff = float(diffs.max()) if len(diffs) else 0.0
    assert max_diff < 1e-4, (
        f"exceeds_six_min_share differs from canonical-recomputed expected by "
        f"max {max_diff:.6f}; suspect denominator regression"
    )

    # And the global weighted share must match the canonical headline (~32.4%).
    recorded_count = (
        borough_summary["incident_count"]
        * borough_summary["response_time_recorded_share"]
    )
    weighted_share = float(
        (borough_summary["exceeds_six_min_share"] * recorded_count).sum()
        / recorded_count.sum()
    )
    canonical_share = float(canonical_rt["exceeds_six_min_target"].mean())
    assert abs(weighted_share - canonical_share) < 1e-3, (
        f"global weighted share {weighted_share:.4f} differs from canonical "
        f"{canonical_share:.4f} by more than 0.001"
    )
