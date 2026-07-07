"""
Build the LFB mobilisations parquet for 2024--2026 by ingesting both
mobilisation files (2021--2024 + 2025 onwards), filtering to the canonical
incident date range, joining against the canonical incident-record artefact
on IncidentNumber, and emitting a join-quality memo.

Inputs:
    data/raw/LFB_Mobilisation_2021_2024.csv  (raw, not committed)
    data/raw/LFB_Mobilisation_2025.csv       (raw, not committed)
    data/raw/Mobilisations_Metadata.xlsx     (raw, not committed; schema reference only)
    data/processed/lfb_canonical_2024_2026.parquet (built by build_canonical.py)

Outputs:
    data/processed/lfb_mobilisations_2024_2026.parquet
    data/processed/lfb_mobilisations_2024_2026_provenance.json
    data/processed/lfb_mobilisations_2024_2026_dictionary.md
    data/processed/lfb_mobilisations_2024_2026_dq_memo.md
    data/processed/lfb_mobilisations_2024_2026_join_quality_memo.md

Run from the project root:
    python src/data/build_mobilisations.py

    Scope:
- This is the **mobilisation minimal loop**: ingest + filter + join + join-quality
  memo. It does NOT introduce a station-coverage / dispatch-optimisation claim
  and does NOT modify the existing dashboard UI. The artefact's purpose is to
  put response-time and deployment evidence on appliance-level mobilisation
  records instead of incident-level summary fields alone, so that §5/§6 prose
  can talk about deployed-from station, pump order, and arrival time without
  silently relying on the official LFB incident dashboard's own derivations.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = PROJECT_ROOT / "data" / "raw"
RAW_2021_2024 = RAW_DIR / "LFB_Mobilisation_2021_2024.csv"
RAW_2025 = RAW_DIR / "LFB_Mobilisation_2025.csv"
RAW_METADATA = RAW_DIR / "Mobilisations_Metadata.xlsx"

CANONICAL_PARQUET = PROJECT_ROOT / "data" / "processed" / "lfb_canonical_2024_2026.parquet"

OUT_DIR = PROJECT_ROOT / "data" / "processed"
OUT_PARQUET = OUT_DIR / "lfb_mobilisations_2024_2026.parquet"
OUT_PROVENANCE = OUT_DIR / "lfb_mobilisations_2024_2026_provenance.json"
OUT_DICTIONARY = OUT_DIR / "lfb_mobilisations_2024_2026_dictionary.md"
OUT_DQ_MEMO = OUT_DIR / "lfb_mobilisations_2024_2026_dq_memo.md"
OUT_JOIN_MEMO = OUT_DIR / "lfb_mobilisations_2024_2026_join_quality_memo.md"

# LFB performance-target threshold for the first-arriving pump, in seconds.
# Same constant as in build_canonical.py.
FIRST_PUMP_TARGET_SECONDS = 360  # = 6 minutes

# Sanity bounds (sec) for AttendanceTimeSeconds. Median should land in this
# band; outside it the unit interpretation has likely changed.
ATTENDANCE_SECONDS_SANITY_MIN = 60
ATTENDANCE_SECONDS_SANITY_MAX = 1500

# Acceptable share of *all* canonical incidents that have at least one
# matching mobilisation row. The remaining incidents are typically those
# without any pump dispatched (FirstPumpArriving_AttendanceTime is NaN);
# they show up in the canonical because LFB still logs the call/incident
# but no appliance was mobilised. Empirically observed at ~94.7% in the
# 2024--2026 window, so the floor is set just below that.
JOIN_COVERAGE_FLOOR_ALL = 0.93

# Stricter floor: among canonical incidents that DO have a recorded
# FirstPumpArriving_AttendanceTime (i.e. a pump was dispatched and arrived),
# we expect a mobilisation row tagged is_first_arriving_pump to be present.
# Empirically ~99.85%; sub-99% suggests join-key drift between the two open-
# data releases.
JOIN_COVERAGE_FLOOR_DISPATCHED = 0.99

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_one_csv(path: Path) -> pd.DataFrame:
    print(f"Reading {path.relative_to(PROJECT_ROOT)} ...", flush=True)
    df = pd.read_csv(path, low_memory=False)
    print(f"  loaded {len(df):,} rows x {df.shape[1]} cols", flush=True)
    return df


def parse_lfb_datetime(series: pd.Series) -> pd.Series:
    """Parse LFB mobilisation dd/mm/yyyy [HH:MM[:SS]] strings to datetime.

    The 2018 sample uses HH:MM:SS; the 2025 sample drops the seconds. Pandas
    'mixed' format with dayfirst=True handles both, and coerces 'NULL' /
    invalid strings to NaT.
    """
    return pd.to_datetime(series, format="mixed", dayfirst=True, errors="coerce")


def add_derived_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    df["mobilised_at"] = parse_lfb_datetime(df["DateAndTimeMobilised"])
    df["mobile_at"] = parse_lfb_datetime(df["DateAndTimeMobile"])
    df["arrived_at"] = parse_lfb_datetime(df["DateAndTimeArrived"])

    # AttendanceTimeSeconds is int64 in raw; alias as float for downstream
    # nullable arithmetic and add a minutes column.
    df["attendance_time_seconds"] = pd.to_numeric(
        df["AttendanceTimeSeconds"], errors="coerce"
    )
    df["attendance_time_minutes"] = df["attendance_time_seconds"] / 60.0

    # PerformanceReporting is dtype object — values "1", "2", ..., possibly
    # empty / NaN. The official LFB performance metric (and incident-record
    # FirstPumpArriving_AttendanceTime) corresponds to PerformanceReporting=1.
    pr = df["PerformanceReporting"].astype("string").str.strip()
    df["is_first_arriving_pump"] = pr.eq("1")

    df["is_first_ordered_pump"] = df["PumpOrder"].eq(1)

    df["exceeds_six_min_target"] = pd.array(
        np.where(
            df["attendance_time_seconds"].isna(),
            pd.NA,
            df["attendance_time_seconds"] > FIRST_PUMP_TARGET_SECONDS,
        ),
        dtype="boolean",
    )

    df["borough_canonical"] = (
        df["BoroughName"].astype("string").str.strip().str.title()
    )

    df["year_month"] = df["mobilised_at"].dt.to_period("M").astype("string")
    df["mobilised_hour"] = df["mobilised_at"].dt.hour.astype("Int8")

    return df


# ---------------------------------------------------------------------------
# Sidecars
# ---------------------------------------------------------------------------


def write_provenance(
    raw_paths: dict[str, Path],
    raw_shas: dict[str, str],
    canonical_sha: str,
    raw_rows_total: int,
    out_rows: int,
    out_cols: list[str],
    date_min: pd.Timestamp | None,
    date_max: pd.Timestamp | None,
) -> None:
    extracted_at = dt.datetime.now(dt.timezone.utc).isoformat()
    provenance = {
        "artefact": "lfb_mobilisations_2024_2026",
        "schema_version": "1.0",
        "sources": [
            {
                "role": role,
                "filename": path.name,
                "relative_path": str(path.relative_to(PROJECT_ROOT)),
                "sha256": raw_shas[role],
            }
            for role, path in raw_paths.items()
        ],
        "publisher": "London Fire Brigade via London Datastore",
        "publisher_urls": [
            "https://data.london.gov.uk/dataset/london-fire-brigade-mobilisation-records",
        ],
        "joined_against": {
            "artefact": "lfb_canonical_2024_2026",
            "relative_path": str(CANONICAL_PARQUET.relative_to(PROJECT_ROOT)),
            "sha256": canonical_sha,
            "join_key": "IncidentNumber",
        },
        "build": {
            "extracted_at_utc": extracted_at,
            "script": str(Path(__file__).relative_to(PROJECT_ROOT)),
            "python_version": sys.version.split()[0],
            "pandas_version": pd.__version__,
        },
        "row_counts": {
            "input_total_pre_filter": raw_rows_total,
            "output_post_filter": out_rows,
            "dropped_by_date_filter": raw_rows_total - out_rows,
        },
        "date_filter": {
            "field": "mobilised_at (parsed from DateAndTimeMobilised)",
            "min_inclusive": str(date_min.date()) if date_min is not None else None,
            "max_inclusive": str(date_max.date()) if date_max is not None else None,
            "rationale": (
                "Filter window is inherited from the canonical incident "
                "DateOfCall min/max, so mobilisation rows match the "
                "incident-level scope used elsewhere in the project."
            ),
        },
        "transformations_applied": [
            "Parsed DateAndTimeMobilised / DateAndTimeMobile / DateAndTimeArrived to datetime (dayfirst=True, format='mixed', errors='coerce')",
            "Filtered mobilised_at to canonical incident date range",
            "Derived attendance_time_seconds (numeric coercion) and attendance_time_minutes",
            "Derived is_first_arriving_pump = (PerformanceReporting == '1')",
            "Derived is_first_ordered_pump = (PumpOrder == 1)",
            "Derived exceeds_six_min_target = nullable boolean (pd.NA where time is NaN)",
            "Derived borough_canonical = BoroughName trimmed + title-cased",
            "Derived year_month, mobilised_hour from mobilised_at",
            "Derived matches_canonical_incident = IncidentNumber present in lfb_canonical_2024_2026 IncidentNumber set, so downstream aggregations cannot silently mix unmatched rows into canonical-window claims",
        ],
        "constants": {
            "first_pump_target_seconds": FIRST_PUMP_TARGET_SECONDS,
            "attendance_seconds_sanity_band": [
                ATTENDANCE_SECONDS_SANITY_MIN,
                ATTENDANCE_SECONDS_SANITY_MAX,
            ],
            "join_coverage_floor_all_incidents": JOIN_COVERAGE_FLOOR_ALL,
            "join_coverage_floor_dispatched_incidents": JOIN_COVERAGE_FLOOR_DISPATCHED,
        },
        "output_columns": out_cols,
        "scope_note": (
            "This artefact is the mobilisation minimal loop. Use it for response/deployment evidence "
            "(deployed-from station, pump order, arrival time). Do not promote "
            "to a station-coverage or dispatch-optimisation claim without "
            "additional routing-grade inputs."
        ),
    }
    OUT_PROVENANCE.write_text(json.dumps(provenance, indent=2, ensure_ascii=False))
    print(f"  wrote {OUT_PROVENANCE.relative_to(PROJECT_ROOT)}", flush=True)


def write_dictionary(df: pd.DataFrame) -> None:
    derived = {
        "mobilised_at": "Parsed DateAndTimeMobilised (datetime, dayfirst=True, GMT per LFB notes).",
        "mobile_at": "Parsed DateAndTimeMobile.",
        "arrived_at": "Parsed DateAndTimeArrived.",
        "attendance_time_seconds": "Numeric coercion of AttendanceTimeSeconds (turn-out + travel, seconds).",
        "attendance_time_minutes": "attendance_time_seconds / 60.",
        "is_first_arriving_pump": "True where PerformanceReporting == '1' (LFB's first-arriving-pump flag, used for the 6-minute target metric and matched against the incident-record FirstPumpArriving_AttendanceTime field).",
        "is_first_ordered_pump": "True where PumpOrder == 1 (first pump in the despatch order; not always the first to arrive).",
        "exceeds_six_min_target": "Nullable boolean: True if attendance_time_seconds > 360, False if <=360, pd.NA if missing. Same semantics as the canonical incident artefact.",
        "borough_canonical": "BoroughName trimmed + title-cased; matches the canonical incident artefact's borough_canonical.",
        "year_month": "Year-month period of mobilised_at as 'YYYY-MM'.",
        "mobilised_hour": "Hour-of-day (0--23) of mobilised_at.",
        "matches_canonical_incident": "True iff this row's IncidentNumber is present in the canonical incident artefact (`data/processed/lfb_canonical_2024_2026.parquet`). False rows are typically cross-boundary mobilisations (LFB attending incidents in Buckinghamshire / Slough / Surrey) or rows from data-vintage drift between the mobilisation and incident open-data releases. Downstream §6 / dashboard aggregations should filter on this flag (or opt in to unmatched rows explicitly) to avoid silently mixing non-canonical incidents into canonical-window claims.",
    }

    lines: list[str] = []
    lines.append("# LFB Mobilisations Dataset Dictionary")
    lines.append("")
    lines.append("> Auto-generated by `src/data/build_mobilisations.py`. Edit the script, not this file.")
    lines.append("")
    lines.append(f"- **Rows**: {len(df):,}")
    lines.append(f"- **Columns**: {df.shape[1]}")
    lines.append("")
    lines.append("## Columns")
    lines.append("")
    lines.append("| Column | Dtype | Non-null | Source | Notes |")
    lines.append("|---|---|---|---|---|")
    for col in df.columns:
        dtype = str(df[col].dtype)
        nonnull = int(df[col].notna().sum())
        source = "derived" if col in derived else "raw (LFB Mobilisation Records)"
        notes = derived.get(col, "")
        lines.append(f"| `{col}` | {dtype} | {nonnull:,} | {source} | {notes} |")
    lines.append("")

    OUT_DICTIONARY.write_text("\n".join(lines))
    print(f"  wrote {OUT_DICTIONARY.relative_to(PROJECT_ROOT)}", flush=True)


def write_dq_memo(df: pd.DataFrame, raw_rows_total: int) -> None:
    n = len(df)
    pct = lambda x: float(x * 100)  # noqa: E731

    rt_present_pct = pct(df["attendance_time_seconds"].notna().mean())
    exceed_among_present = pct(
        df.loc[df["attendance_time_seconds"].notna(), "exceeds_six_min_target"].mean()
    )
    first_arriving_share = pct(df["is_first_arriving_pump"].mean())
    first_ordered_share = pct(df["is_first_ordered_pump"].mean())
    matches_canonical_pct = pct(df["matches_canonical_incident"].mean())
    unmatched_count = int((~df["matches_canonical_incident"]).sum())

    deployed_top = (
        df["DeployedFromStation_Name"]
        .value_counts(dropna=False)
        .head(15)
    )

    location_share = (
        df["DeployedFromLocation"].value_counts(normalize=True).mul(100).round(2)
    )

    delay_share = (
        df["DelayCode_Description"]
        .fillna("(no delay)")
        .value_counts(normalize=True)
        .mul(100)
        .round(2)
        .head(8)
    )

    date_min = df["mobilised_at"].min() if df["mobilised_at"].notna().any() else None
    date_max = df["mobilised_at"].max() if df["mobilised_at"].notna().any() else None

    lines: list[str] = []
    lines.append("# LFB Mobilisations Dataset — Data Quality Memo")
    lines.append("")
    lines.append("> Auto-generated by `src/data/build_mobilisations.py`. Reusable in `report/.../contents/implementation.tex` (\\S5.2/\\S5.3).")
    lines.append("")
    lines.append("## Scope")
    lines.append("")
    lines.append(f"- Raw inputs (combined): {raw_rows_total:,} rows across `LFB_Mobilisation_2021_2024.csv` + `LFB_Mobilisation_2025.csv`.")
    lines.append(f"- Filtered output: `data/processed/lfb_mobilisations_2024_2026.parquet`, {n:,} rows.")
    lines.append(f"- Date range of mobilised_at after filter: {date_min} -- {date_max}.")
    lines.append("")
    lines.append("## Headline numbers")
    lines.append("")
    lines.append(f"- **Mobilisation records in 2024--2026 window**: {n:,}.")
    lines.append(f"- **Records with a parsed AttendanceTimeSeconds**: {rt_present_pct:.1f}\\%.")
    lines.append(f"- **Attendance time exceeds the 6-minute target** (among records with a recorded time): {exceed_among_present:.1f}\\%.")
    lines.append(f"- **Rows flagged as first-arriving pump** (`PerformanceReporting == '1'`): {first_arriving_share:.1f}\\%.")
    lines.append(f"- **Rows flagged as first-ordered pump** (`PumpOrder == 1`): {first_ordered_share:.1f}\\%.")
    lines.append(f"- **Rows whose `IncidentNumber` matches the canonical incident artefact** (`matches_canonical_incident`): {matches_canonical_pct:.2f}\\%; the remaining {unmatched_count:,} rows are typically cross-boundary mobilisations into adjoining authorities (Buckinghamshire / Slough / Surrey) or rows from data-vintage drift between the two open-data releases. Downstream §6 / dashboard aggregations should filter on `matches_canonical_incident` to avoid silently mixing non-canonical incidents into canonical-window claims.")
    lines.append("")
    lines.append("## DeployedFromLocation share")
    lines.append("")
    lines.append("| Location | Share |")
    lines.append("|---|---|")
    for loc, p in location_share.items():
        loc_str = "(missing)" if pd.isna(loc) else str(loc)
        lines.append(f"| {loc_str} | {p:.2f}\\% |")
    lines.append("")
    lines.append("## Top 15 deploying stations")
    lines.append("")
    lines.append("| Station | Mobilisations |")
    lines.append("|---|---|")
    for stn, c in deployed_top.items():
        stn_str = "(missing)" if pd.isna(stn) else str(stn)
        lines.append(f"| {stn_str} | {c:,} |")
    lines.append("")
    lines.append("## Delay-code top 8 (descending)")
    lines.append("")
    lines.append("| Delay code | Share |")
    lines.append("|---|---|")
    for code, p in delay_share.items():
        lines.append(f"| {code} | {p:.2f}\\% |")
    lines.append("")
    lines.append("## Known limitations to surface")
    lines.append("")
    lines.append("1. **Mobilisation-level vs incident-level units.** Each row is one appliance mobilisation. Counting incidents requires `groupby('IncidentNumber')`; counting fairness/coverage at appliance level requires keeping rows. Both are valid; do not silently switch units between paragraphs. When restricting to the canonical incident scope, filter on `matches_canonical_incident` first.")
    lines.append("2. **First-arriving vs first-ordered.** `is_first_arriving_pump` (PerformanceReporting=='1') is the LFB performance metric used for the 6-min target. `is_first_ordered_pump` (PumpOrder==1) is the dispatch order. They usually agree but can diverge under delays; choose one explicitly per analysis and state it in prose.")
    lines.append("3. **DateAndTimeReturned is sparsely populated** in the raw releases (often `NULL`). The current pipeline does not parse it; total-time-on-incident analyses are out of scope.")
    lines.append("4. **No coordinate fields.** Mobilisation records do not include incident coordinates; spatial analyses must join back to the incident canonical (`Easting_m`/`Northing_m` or the rounded family).")
    lines.append("5. **DeployedFromLocation is qualitative** (Home Station / Other Station / etc.); it is not a deployment-distance proxy. The §5.5 assignment-footprint proxy + §5.6 D1 station-location recovery remain the route to a deployment-distance claim.")
    lines.append("")

    OUT_DQ_MEMO.write_text("\n".join(lines))
    print(f"  wrote {OUT_DQ_MEMO.relative_to(PROJECT_ROOT)}", flush=True)


def write_join_quality_memo(
    df: pd.DataFrame,
    canonical: pd.DataFrame,
) -> dict[str, float]:
    """Compute and persist join-quality stats. Returns dict for validation checks."""

    canonical_inc = canonical["IncidentNumber"].astype("string")
    mob_inc = df["IncidentNumber"].astype("string")

    canonical_set = set(canonical_inc.dropna().unique())
    mob_set = set(mob_inc.dropna().unique())

    mobs_with_match = mob_inc.isin(canonical_set).sum()
    mobs_total = len(df)
    mobs_match_share = float(mobs_with_match) / mobs_total if mobs_total else 0.0

    incidents_with_any_mob = len(canonical_set & mob_set)
    incidents_match_share = (
        incidents_with_any_mob / len(canonical_set) if canonical_set else 0.0
    )

    # First-arriving cross-check.
    first_arriving = df.loc[
        df["is_first_arriving_pump"] & df["IncidentNumber"].notna(),
        ["IncidentNumber", "attendance_time_seconds"],
    ].copy()
    # Some incidents have multiple rows tagged is_first_arriving (rare); collapse
    # to the minimum AttendanceTimeSeconds per incident, which is the safest
    # interpretation of the LFB performance metric for cross-checking.
    first_arriving_grouped = (
        first_arriving.groupby("IncidentNumber")["attendance_time_seconds"]
        .min()
        .rename("mob_first_arriving_seconds")
    )

    canonical_first_pump = canonical[
        ["IncidentNumber", "FirstPumpArriving_AttendanceTime"]
    ].dropna(subset=["FirstPumpArriving_AttendanceTime"]).copy()
    canonical_first_pump["IncidentNumber"] = canonical_first_pump["IncidentNumber"].astype("string")

    cross = canonical_first_pump.merge(
        first_arriving_grouped,
        left_on="IncidentNumber",
        right_index=True,
        how="left",
    )
    cross["diff_seconds"] = (
        cross["mob_first_arriving_seconds"] - cross["FirstPumpArriving_AttendanceTime"]
    )

    cross_have_both = cross["mob_first_arriving_seconds"].notna()
    cross_match_share = float(cross_have_both.mean()) if len(cross) else 0.0

    diffs = cross.loc[cross_have_both, "diff_seconds"]
    if len(diffs):
        diff_abs_median = float(diffs.abs().median())
        diff_within_5s = float((diffs.abs() <= 5).mean())
        diff_within_30s = float((diffs.abs() <= 30).mean())
    else:
        diff_abs_median = float("nan")
        diff_within_5s = float("nan")
        diff_within_30s = float("nan")

    pumps_per_incident = (
        df.dropna(subset=["IncidentNumber"]).groupby("IncidentNumber").size()
    )
    pumps_per_incident_summary = {
        "p50": int(pumps_per_incident.median()) if len(pumps_per_incident) else 0,
        "p90": int(pumps_per_incident.quantile(0.9)) if len(pumps_per_incident) else 0,
        "max": int(pumps_per_incident.max()) if len(pumps_per_incident) else 0,
    }

    lines: list[str] = []
    lines.append("# LFB Mobilisations — Join-Quality Memo")
    lines.append("")
    lines.append("> Auto-generated by `src/data/build_mobilisations.py`.")
    lines.append("")
    lines.append("Reports how the mobilisation parquet joins back to the canonical incident artefact (`lfb_canonical_2024_2026.parquet`) on `IncidentNumber`. Numbers below are the evidence base for any §5/§6 claim that uses appliance-level fields (deployed-from station, attendance time, pump order); reproduce by re-running the build script.")
    lines.append("")
    lines.append("## Mobilisation-side coverage")
    lines.append("")
    lines.append(f"- **Mobilisation rows in window**: {mobs_total:,}.")
    lines.append(f"- **Rows whose IncidentNumber matches a canonical incident**: {mobs_with_match:,} ({mobs_match_share*100:.2f}\\%).")
    lines.append(f"- **Distinct mobilisation IncidentNumbers**: {len(mob_set):,}.")
    lines.append("")
    lines.append("## Incident-side coverage")
    lines.append("")
    lines.append(f"- **Canonical incidents in 2024--2026**: {len(canonical_set):,}.")
    lines.append(f"- **Canonical incidents with at least one mobilisation row**: {incidents_with_any_mob:,} ({incidents_match_share*100:.2f}\\%).")
    lines.append(f"- **Acceptance floor (all incidents)**: {JOIN_COVERAGE_FLOOR_ALL*100:.0f}\\% (validation-check threshold). Gap is dominated by canonical rows with no `FirstPumpArriving_AttendanceTime` -- i.e.\\ incidents where no pump was dispatched / arrived (cancelled calls, false alarms not requiring response). They are correctly absent from the mobilisation file and should not be treated as join failures.")
    lines.append("")
    lines.append("## First-arriving-pump cross-check vs canonical `FirstPumpArriving_AttendanceTime`")
    lines.append("")
    lines.append("This is the strict denominator for response/deployment claims: among canonical incidents where a first pump actually arrived, a mobilisation row with `is_first_arriving_pump = True` should exist and its `attendance_time_seconds` should match the canonical's `FirstPumpArriving_AttendanceTime`.")
    lines.append("")
    lines.append(f"- Canonical incidents with a recorded first-pump time: {len(canonical_first_pump):,}.")
    lines.append(f"- Of those, share with at least one mobilisation row flagged `is_first_arriving_pump`: {cross_match_share*100:.2f}\\%.")
    lines.append(f"- Acceptance floor (dispatched incidents): {JOIN_COVERAGE_FLOOR_DISPATCHED*100:.0f}\\% (validation-check threshold).")
    lines.append(f"- Median absolute diff (mob first-arriving min vs canonical FirstPumpArriving_AttendanceTime), seconds: {diff_abs_median:.1f}.")
    lines.append(f"- Share within 5\\,s of canonical: {diff_within_5s*100:.2f}\\%.")
    lines.append(f"- Share within 30\\,s of canonical: {diff_within_30s*100:.2f}\\%.")
    lines.append("")
    lines.append("Interpretation: the canonical's `FirstPumpArriving_AttendanceTime` field is itself derived from the same upstream operational system as `PerformanceReporting=1` rows here, so values are expected to be identical or very close. Diffs above 30\\,s suggest either a data-vintage mismatch between the two open-data releases or a denominator difference (multiple performance flags per incident); inspect cases before publishing claims.")
    lines.append("")
    lines.append("## Pumps per incident (mobilisation rows per IncidentNumber)")
    lines.append("")
    lines.append(f"- Median: {pumps_per_incident_summary['p50']}")
    lines.append(f"- 90th percentile: {pumps_per_incident_summary['p90']}")
    lines.append(f"- Max: {pumps_per_incident_summary['max']}")
    lines.append("")
    lines.append("Note: incidents in the canonical with `NumPumpsAttending` should approximately equal the count of mobilisation rows for that IncidentNumber. Large divergences are expected for sustained incidents (re-mobilisations, relief crews) and for incidents whose `NumPumpsAttending` field was set at a different snapshot than the mobilisation-records release.")
    lines.append("")

    OUT_JOIN_MEMO.write_text("\n".join(lines))
    print(f"  wrote {OUT_JOIN_MEMO.relative_to(PROJECT_ROOT)}", flush=True)

    return {
        "mobs_match_share": mobs_match_share,
        "incidents_match_share": incidents_match_share,
        "cross_match_share": cross_match_share,
        "diff_abs_median": diff_abs_median,
    }


# ---------------------------------------------------------------------------
# Validation checks
# ---------------------------------------------------------------------------


def validation_checks(df: pd.DataFrame, join_stats: dict[str, float]) -> None:
    print("Running validation checks ...", flush=True)

    # 1. Non-empty.
    assert len(df) > 0, "mobilisations dataset is empty"

    # 2. Required columns present.
    required = {
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
        # derived
        "mobilised_at",
        "arrived_at",
        "attendance_time_seconds",
        "attendance_time_minutes",
        "is_first_arriving_pump",
        "is_first_ordered_pump",
        "exceeds_six_min_target",
        "borough_canonical",
        "year_month",
        "matches_canonical_incident",
    }
    missing = required - set(df.columns)
    assert not missing, f"missing required columns: {sorted(missing)}"

    # 3. mobilised_at parsed as datetime.
    assert pd.api.types.is_datetime64_any_dtype(df["mobilised_at"]), "mobilised_at not datetime"

    # 4. AttendanceTimeSeconds median in sanity band.
    rt = df["attendance_time_seconds"].dropna()
    assert len(rt) > 0, "no attendance_time_seconds values present"
    median_rt = float(rt.median())
    assert ATTENDANCE_SECONDS_SANITY_MIN <= median_rt <= ATTENDANCE_SECONDS_SANITY_MAX, (
        f"median attendance_time_seconds={median_rt:.1f}s outside sanity band "
        f"{ATTENDANCE_SECONDS_SANITY_MIN}--{ATTENDANCE_SECONDS_SANITY_MAX}s"
    )

    # 5. is_first_arriving_pump should be ~1 of 1-N pumps per incident, so
    # share is roughly 1/mean_pumps. Bound it loosely on each side.
    fa_share = float(df["is_first_arriving_pump"].mean())
    assert 0.20 <= fa_share <= 0.95, (
        f"is_first_arriving_pump share={fa_share:.2f} outside sanity band 0.20--0.95; "
        "PerformanceReporting parsing or filter may have changed"
    )

    # 6. All-incident join coverage floor. The remaining gap is canonical
    # rows with no first-pump time (no appliance dispatched), so this floor
    # is loose; the strict check is in (7).
    incidents_match_share = join_stats["incidents_match_share"]
    assert incidents_match_share >= JOIN_COVERAGE_FLOOR_ALL, (
        f"all-incident join coverage={incidents_match_share*100:.2f}% < "
        f"floor {JOIN_COVERAGE_FLOOR_ALL*100:.0f}%; if this drops, suspect either "
        "an IncidentNumber join-key drift between the two open-data releases or "
        "an unusual share of cancelled / no-dispatch incidents in the canonical"
    )

    # 7. STRICT: among canonical incidents WITH a recorded first-pump time
    # we expect a mobilisation row tagged is_first_arriving_pump for ~all
    # of them, because both fields trace back to the same operational system.
    cross_match_share = join_stats["cross_match_share"]
    assert cross_match_share >= JOIN_COVERAGE_FLOOR_DISPATCHED, (
        f"dispatched-incident first-arriving cross-check coverage="
        f"{cross_match_share*100:.2f}% < floor {JOIN_COVERAGE_FLOOR_DISPATCHED*100:.0f}%; "
        "PerformanceReporting flag may be inconsistent across files"
    )

    # 8. matches_canonical_incident sum equals the mobilisation-side join
    # count reported in the join-quality memo. Any drift means the parquet
    # column and the memo were computed against different canonical sets.
    flag_share = float(df["matches_canonical_incident"].mean())
    mobs_match_share = join_stats["mobs_match_share"]
    assert abs(flag_share - mobs_match_share) < 1e-9, (
        f"matches_canonical_incident share={flag_share*100:.4f}% drifted from "
        f"join-quality memo mob-side share={mobs_match_share*100:.4f}%"
    )
    # Must dominate the floor used for the row-side test (>=99%); this is the
    # mobilisation-side strict floor, not the all-incident loose floor.
    assert flag_share >= 0.99, (
        f"matches_canonical_incident share={flag_share*100:.2f}% < 99% strict "
        "floor; join-key drift between mobilisation and canonical releases?"
    )

    print("  all validation checks passed", flush=True)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    for path in (RAW_2021_2024, RAW_2025, CANONICAL_PARQUET):
        if not path.exists():
            print(f"ERROR: required input not found at {path}", file=sys.stderr)
            return 2

    raw_shas = {
        "mobilisation_2021_2024": sha256_of(RAW_2021_2024),
        "mobilisation_2025": sha256_of(RAW_2025),
        "metadata_xlsx": sha256_of(RAW_METADATA) if RAW_METADATA.exists() else "(absent)",
    }
    canonical_sha = sha256_of(CANONICAL_PARQUET)

    df_a = load_one_csv(RAW_2021_2024)
    df_b = load_one_csv(RAW_2025)
    raw_rows_total_pre_filter = len(df_a) + len(df_b)
    df_combined = pd.concat([df_a, df_b], ignore_index=True)
    print(f"Combined raw shape: {df_combined.shape}", flush=True)

    df_derived = add_derived_columns(df_combined)

    # Filter to canonical date range.
    print(f"Reading {CANONICAL_PARQUET.relative_to(PROJECT_ROOT)} for date / IncidentNumber scope ...", flush=True)
    canonical = pd.read_parquet(
        CANONICAL_PARQUET,
        columns=["IncidentNumber", "DateOfCall", "FirstPumpArriving_AttendanceTime"],
    )
    date_min = canonical["DateOfCall"].min()
    date_max = canonical["DateOfCall"].max()
    print(f"  canonical date range: {date_min.date()} -- {date_max.date()}", flush=True)

    in_window = df_derived["mobilised_at"].between(
        date_min, date_max + pd.Timedelta(days=1), inclusive="left"
    )
    df_filtered = df_derived.loc[in_window].copy()
    print(
        f"After date filter: {len(df_filtered):,} rows "
        f"(dropped {len(df_derived) - len(df_filtered):,})",
        flush=True,
    )

    # Add matches_canonical_incident flag. Emitting the full date-filtered
    # mobilisation table without a join flag risks downstream aggregations silently mixing
    # cross-boundary mobilisations (LFB attending incidents in adjoining
    # authorities) and any data-vintage drift rows into canonical-window
    # claims. The flag makes the matched / unmatched partition explicit so
    # consumers must either filter on it or opt in to unmatched rows.
    canonical_incident_set = set(
        canonical["IncidentNumber"].astype("string").dropna().unique()
    )
    df_filtered["matches_canonical_incident"] = (
        df_filtered["IncidentNumber"]
        .astype("string")
        .isin(canonical_incident_set)
        .astype(bool)
    )
    matched_count = int(df_filtered["matches_canonical_incident"].sum())
    unmatched_count = len(df_filtered) - matched_count
    print(
        f"matches_canonical_incident: {matched_count:,} matched / "
        f"{unmatched_count:,} unmatched",
        flush=True,
    )

    print(f"Writing {OUT_PARQUET.relative_to(PROJECT_ROOT)} ...", flush=True)
    df_filtered.to_parquet(OUT_PARQUET, index=False)
    print(f"  wrote {len(df_filtered):,} rows x {df_filtered.shape[1]} cols", flush=True)

    write_provenance(
        raw_paths={
            "mobilisation_2021_2024": RAW_2021_2024,
            "mobilisation_2025": RAW_2025,
            "metadata_xlsx": RAW_METADATA,
        },
        raw_shas=raw_shas,
        canonical_sha=canonical_sha,
        raw_rows_total=raw_rows_total_pre_filter,
        out_rows=len(df_filtered),
        out_cols=list(df_filtered.columns),
        date_min=date_min,
        date_max=date_max,
    )
    write_dictionary(df_filtered)
    write_dq_memo(df_filtered, raw_rows_total_pre_filter)
    join_stats = write_join_quality_memo(df_filtered, canonical)

    validation_checks(df_filtered, join_stats)

    print("Done.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
