"""
Build the canonical LFB processed parquet from the raw 2024-onwards Excel.

Input:  data/LFB_Incident_2024_onwards.xlsx (raw open-data download from London Datastore)
Output: data/processed/lfb_canonical_2024_2026.parquet (canonical analytic artefact)
        data/processed/lfb_canonical_2024_2026_provenance.json
        data/processed/lfb_canonical_2024_2026_dictionary.md
        data/processed/lfb_canonical_2024_2026_dq_memo.md

Run from the project root:
    python src/data/build_canonical.py

Reproducibility:
- All filtering rules and derived-column definitions are encoded as module-level
  constants so they can be reviewed and audited.
- Provenance (source filename, source SHA-256, extraction timestamp, input/output
  row counts, transformations applied) is written to a JSON sidecar.
- Validation checks at the end raise AssertionError if invariants are violated;
  the script exits non-zero to fail fast in CI / supervisor review.
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
RAW_PATH = PROJECT_ROOT / "data" / "LFB_Incident_2024_onwards.xlsx"
OUT_DIR = PROJECT_ROOT / "data" / "processed"
OUT_PARQUET = OUT_DIR / "lfb_canonical_2024_2026.parquet"
OUT_PROVENANCE = OUT_DIR / "lfb_canonical_2024_2026_provenance.json"
OUT_DICTIONARY = OUT_DIR / "lfb_canonical_2024_2026_dictionary.md"
OUT_DQ_MEMO = OUT_DIR / "lfb_canonical_2024_2026_dq_memo.md"

# Greater London OSGB36 bounding box (Easting/Northing in metres). Sources:
# Ordnance Survey OS Open data; bbox enlarged to cover the M25 ring road so
# we do not falsely reject incidents on the M25 boundary.
GL_EASTING_MIN = 500_000
GL_EASTING_MAX = 565_000
GL_NORTHING_MIN = 155_000
GL_NORTHING_MAX = 210_000

# LFB attendance-target threshold for the first pump, in seconds.
FIRST_PUMP_TARGET_SECONDS = 360  # = 6 minutes

# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_raw(path: Path) -> pd.DataFrame:
    print(f"Reading {path.relative_to(PROJECT_ROOT)} ...", flush=True)
    df = pd.read_excel(path)
    print(f"  loaded {len(df):,} rows x {df.shape[1]} cols", flush=True)
    return df


def add_derived_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # Date / time parsing.
    df["DateOfCall"] = pd.to_datetime(df["DateOfCall"], errors="coerce")

    # Some response-time-derived fields use TimeOfCall (HH:MM:SS) when present.
    if "TimeOfCall" in df.columns:
        # TimeOfCall is a python time object in openpyxl-loaded sheets; coerce
        # it via a string round-trip to extract the hour reliably.
        df["hour_of_day"] = pd.to_datetime(
            df["TimeOfCall"].astype(str), format="%H:%M:%S", errors="coerce"
        ).dt.hour.astype("Int8")
    else:
        df["hour_of_day"] = pd.NA

    df["year_month"] = df["DateOfCall"].dt.to_period("M").astype(str)
    df["day_of_week"] = df["DateOfCall"].dt.dayofweek.astype("Int8")
    df["weekday_name"] = df["DateOfCall"].dt.day_name()
    df["is_weekend"] = df["day_of_week"].isin([5, 6])

    # Response time in clearer units. Source field is in seconds but the column
    # name does not say so; this is a known dataset caveat. We surface both.
    df["response_time_seconds"] = pd.to_numeric(
        df.get("FirstPumpArriving_AttendanceTime"), errors="coerce"
    )
    df["response_time_minutes"] = df["response_time_seconds"] / 60.0
    # IMPORTANT: nullable boolean. When response_time_seconds is NaN, the
    # exceedance question is undefined -- use pd.NA, NOT False. Otherwise any
    # downstream `.mean()` aggregation silently treats missing-time rows as
    # non-exceedances and deflates the share.
    rt = df["response_time_seconds"]
    df["exceeds_six_min_target"] = pd.array(
        np.where(rt.isna(), pd.NA, rt > FIRST_PUMP_TARGET_SECONDS),
        dtype="boolean",
    )

    # Coordinate validity. The LFB open dataset releases TWO families of
    # coordinates that must not be conflated:
    #
    # * `Easting_m` / `Northing_m` (and `Latitude` / `Longitude`, `Postcode_full`)
    #   are the *precise* per-incident coordinates and are withheld for ~62% of
    #   records for privacy. Use this for fine-grained density / kernel maps.
    #
    # * `Easting_rounded` / `Northing_rounded` are coordinates rounded to a
    #   100 m grid and are released for 100% of records. Use this for borough-
    #   or grid-level aggregation.
    #
    # We expose both as boolean flags so downstream code can pick the right
    # granularity instead of silently dropping records.
    east_p = pd.to_numeric(df.get("Easting_m"), errors="coerce")
    north_p = pd.to_numeric(df.get("Northing_m"), errors="coerce")
    df["coord_precise_valid"] = (
        east_p.between(GL_EASTING_MIN, GL_EASTING_MAX, inclusive="both")
        & north_p.between(GL_NORTHING_MIN, GL_NORTHING_MAX, inclusive="both")
    )

    east_r = pd.to_numeric(df.get("Easting_rounded"), errors="coerce")
    north_r = pd.to_numeric(df.get("Northing_rounded"), errors="coerce")
    df["coord_rounded_valid"] = (
        east_r.between(GL_EASTING_MIN, GL_EASTING_MAX, inclusive="both")
        & north_r.between(GL_NORTHING_MIN, GL_NORTHING_MAX, inclusive="both")
    )

    # Borough name normalisation: strip + title-case to handle the
    # "RICHMOND UPON THAMES" vs "Richmond upon Thames" inconsistency.
    if "IncGeo_BoroughName" in df.columns:
        df["borough_canonical"] = (
            df["IncGeo_BoroughName"].astype("string").str.strip().str.title()
        )

    return df


def write_provenance(
    raw_path: Path,
    raw_sha256: str,
    raw_rows: int,
    out_rows: int,
    out_cols: list[str],
) -> None:
    extracted_at = dt.datetime.now(dt.timezone.utc).isoformat()
    provenance = {
        "artefact": "lfb_canonical_2024_2026",
        "schema_version": "1.0",
        "source": {
            "filename": raw_path.name,
            "relative_path": str(raw_path.relative_to(PROJECT_ROOT)),
            "sha256": raw_sha256,
            "publisher": "London Fire Brigade via London Datastore",
            "publisher_url": "https://data.london.gov.uk/dataset/london-fire-brigade-incident-records",
        },
        "build": {
            "extracted_at_utc": extracted_at,
            "script": str(Path(__file__).relative_to(PROJECT_ROOT)),
            "python_version": sys.version.split()[0],
            "pandas_version": pd.__version__,
        },
        "row_counts": {
            "input": raw_rows,
            "output": out_rows,
            "dropped": raw_rows - out_rows,
        },
        "transformations_applied": [
            "DateOfCall parsed to datetime (errors='coerce')",
            "Derived: hour_of_day from TimeOfCall",
            "Derived: year_month, day_of_week, weekday_name, is_weekend",
            "Derived: response_time_seconds (alias) + response_time_minutes",
            "Derived: exceeds_six_min_target = response_time_seconds > 360 (nullable boolean: pd.NA where response_time_seconds is NaN, so downstream mean() correctly skips missing-time rows)",
            "Derived: coord_precise_valid = Easting_m + Northing_m both within Greater London bbox (precise per-incident, ~37.9%)",
            "Derived: coord_rounded_valid = Easting_rounded + Northing_rounded both within Greater London bbox (100m grid, ~100%)",
            "Derived: borough_canonical = IncGeo_BoroughName trimmed + title-cased",
        ],
        "constants": {
            "first_pump_target_seconds": FIRST_PUMP_TARGET_SECONDS,
            "greater_london_bbox_osgb36": {
                "easting_min": GL_EASTING_MIN,
                "easting_max": GL_EASTING_MAX,
                "northing_min": GL_NORTHING_MIN,
                "northing_max": GL_NORTHING_MAX,
            },
        },
        "output_columns": out_cols,
    }
    OUT_PROVENANCE.write_text(json.dumps(provenance, indent=2, ensure_ascii=False))
    print(f"  wrote {OUT_PROVENANCE.relative_to(PROJECT_ROOT)}", flush=True)


def write_dictionary(df: pd.DataFrame) -> None:
    derived = {
        "hour_of_day": "Hour-of-day (0--23) parsed from TimeOfCall.",
        "year_month": "Year-month period as 'YYYY-MM' string for grouping.",
        "day_of_week": "Day-of-week index (Monday=0, Sunday=6).",
        "weekday_name": "Day-of-week name in English.",
        "is_weekend": "True if Saturday or Sunday.",
        "response_time_seconds": "Numeric coercion of FirstPumpArriving_AttendanceTime (seconds).",
        "response_time_minutes": "response_time_seconds / 60.",
        "exceeds_six_min_target": "Nullable boolean. True if response_time_seconds > 360 (the LFB 6-minute first-pump target); False if response_time_seconds <= 360; pd.NA if response_time_seconds is NaN. Downstream `.mean()` therefore returns the share of incidents *with a recorded time* that exceeded the target -- not the share of all incidents (which would silently treat missing-time rows as non-exceedances).",
        "coord_precise_valid": "True iff Easting_m and Northing_m (the precise per-incident coordinates, withheld by LFB for ~62% of records on privacy grounds) are both present and inside the Greater London OSGB36 bbox. Use for density / kernel-style mapping.",
        "coord_rounded_valid": "True iff Easting_rounded and Northing_rounded (coordinates rounded to a 100m grid, released for ~100% of records) are both present and inside the Greater London OSGB36 bbox. Use for borough- or grid-level aggregation.",
        "borough_canonical": "IncGeo_BoroughName with whitespace stripped and title-cased to canonicalise capitalisation variants.",
    }

    lines: list[str] = []
    lines.append("# LFB Canonical Dataset Dictionary")
    lines.append("")
    lines.append("> Auto-generated by `src/data/build_canonical.py`. Edit the script, not this file.")
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
        source = "derived" if col in derived else "raw (LFB Incident Records)"
        notes = derived.get(col, "")
        lines.append(f"| `{col}` | {dtype} | {nonnull:,} | {source} | {notes} |")
    lines.append("")

    OUT_DICTIONARY.write_text("\n".join(lines))
    print(f"  wrote {OUT_DICTIONARY.relative_to(PROJECT_ROOT)}", flush=True)


def write_dq_memo(df: pd.DataFrame, raw_rows: int) -> None:
    coord_precise_pct = float(df["coord_precise_valid"].mean() * 100)
    coord_rounded_pct = float(df["coord_rounded_valid"].mean() * 100)
    rt_present = df["response_time_seconds"].notna()
    rt_present_pct = float(rt_present.mean() * 100)
    exceed_among_present = float(
        df.loc[rt_present, "exceeds_six_min_target"].mean() * 100
    )

    inc_group_pct = (
        df["IncidentGroup"].value_counts(normalize=True).mul(100).round(2)
    )

    pumps_by_group = (
        df.groupby("IncidentGroup")["NumPumpsAttending"]
        .mean()
        .round(2)
        .to_dict()
    )

    date_min = df["DateOfCall"].min().date() if df["DateOfCall"].notna().any() else None
    date_max = df["DateOfCall"].max().date() if df["DateOfCall"].notna().any() else None

    lines: list[str] = []
    lines.append("# LFB Canonical Dataset — Data Quality Memo")
    lines.append("")
    lines.append("> Auto-generated by `src/data/build_canonical.py`. Reusable in `report/.../contents/background.tex` (\\S3.3) and `implementation.tex` (\\S5.2).")
    lines.append("")
    lines.append("## Scope")
    lines.append("")
    lines.append(f"- Raw input: `data/LFB_Incident_2024_onwards.xlsx`, {raw_rows:,} rows.")
    lines.append(f"- Canonical output: `data/processed/lfb_canonical_2024_2026.parquet`, {len(df):,} rows.")
    lines.append(f"- Date range: {date_min} -- {date_max}.")
    lines.append("")
    lines.append("## Headline numbers (these are quoted in `contents/introduction.tex` \\S1.1)")
    lines.append("")
    lines.append(f"- **Total incidents in slice**: {len(df):,}.")
    lines.append(f"- **Records with precise per-incident coordinates** (`Easting_m` / `Northing_m`, used for kernel-density mapping): {coord_precise_pct:.1f}\\%. The remaining ~{100 - coord_precise_pct:.0f}\\% have these fields withheld by LFB for privacy.")
    lines.append(f"- **Records with rounded 100\\,m-grid coordinates** (`Easting_rounded` / `Northing_rounded`, used for borough- or grid-level aggregation): {coord_rounded_pct:.1f}\\%.")
    lines.append(f"- **Records with a recorded first-pump attendance time**: {rt_present_pct:.1f}\\%.")
    lines.append(f"- **First-pump time exceeds the 6-minute target** (among records with a recorded time): {exceed_among_present:.1f}\\%.")
    lines.append("")
    lines.append("## Incident-group composition")
    lines.append("")
    lines.append("| Incident group | Share |")
    lines.append("|---|---|")
    for group, pct in inc_group_pct.items():
        lines.append(f"| {group} | {pct:.2f}\\% |")
    lines.append("")
    lines.append("## Mean pumps attending, by incident group")
    lines.append("")
    lines.append("| Incident group | Mean NumPumpsAttending |")
    lines.append("|---|---|")
    for group, mean_pumps in pumps_by_group.items():
        lines.append(f"| {group} | {mean_pumps} |")
    lines.append("")
    lines.append("## Known limitations to surface in the dashboard")
    lines.append("")
    lines.append("1. **Two coordinate families exist and must not be conflated.** `Easting_m` / `Northing_m` (precise) is withheld for ~62\\% of records on privacy grounds; `Easting_rounded` / `Northing_rounded` (100\\,m grid) is released for ~100\\%. Borough- and ward-level analysis can use the rounded family without bias; kernel-density and street-level mapping must use the precise family and acknowledge the 62\\% gap as missing-not-at-random (incidents in dense central areas, where individuals are more identifiable, are more likely to have their precise coordinates suppressed).")
    lines.append("2. **Response time recorded in seconds despite the column name not stating units**. The canonical adds `response_time_seconds` and `response_time_minutes` to remove ambiguity in downstream code.")
    lines.append("3. **2014 closure cohort cannot be directly cross-checked from this slice** because the time window (2024--2026) is entirely post-closure. Comparison to Taylor's pre/post-closure modelling (\\S2.4) is therefore qualitative; cross-check against the borough-level effect direction, not the absolute level.")
    lines.append("4. **NumPumpsAttending is per-incident**, not per-mobilisation. Multi-mobilisation analyses (e.g.\\ how many pumps were eventually deployed for a sustained fire) require joining the LFB Mobilisation Records dataset, which is out of scope for this canonical.")
    lines.append("")

    OUT_DQ_MEMO.write_text("\n".join(lines))
    print(f"  wrote {OUT_DQ_MEMO.relative_to(PROJECT_ROOT)}", flush=True)


# ---------------------------------------------------------------------------
# Validation checks
# ---------------------------------------------------------------------------


def validation_checks(df: pd.DataFrame) -> None:
    print("Running validation checks ...", flush=True)

    # 1. Non-empty.
    assert len(df) > 0, "canonical dataset is empty"

    # 2. Expected key columns present.
    required = {
        "DateOfCall",
        "IncidentGroup",
        "IncGeo_BoroughName",
        "FirstPumpArriving_AttendanceTime",
        "NumPumpsAttending",
        "Easting_m",
        "Northing_m",
        "Easting_rounded",
        "Northing_rounded",
        # derived
        "response_time_seconds",
        "response_time_minutes",
        "exceeds_six_min_target",
        "coord_precise_valid",
        "coord_rounded_valid",
        "borough_canonical",
        "year_month",
        "hour_of_day",
        "is_weekend",
    }
    missing = required - set(df.columns)
    assert not missing, f"missing required columns: {sorted(missing)}"

    # 3. Date column parsed.
    assert pd.api.types.is_datetime64_any_dtype(df["DateOfCall"]), "DateOfCall not datetime"

    # 4. Response-time units sanity (seconds, not ms; not minutes mistakenly).
    rt = df["response_time_seconds"].dropna()
    if len(rt) > 0:
        median_rt = float(rt.median())
        assert 60 <= median_rt <= 1200, (
            f"median response_time_seconds={median_rt:.1f}s outside sanity band 60--1200s; "
            "units may be wrong"
        )

    # 5. Coordinate share sanity. Precise coords (~37.9%) and rounded coords
    # (~100%) are released by LFB at different rates -- check both bands.
    precise_pct = float(df["coord_precise_valid"].mean() * 100)
    rounded_pct = float(df["coord_rounded_valid"].mean() * 100)
    assert 25 <= precise_pct <= 50, (
        f"coord_precise_valid share={precise_pct:.1f}% outside sanity band "
        "25--50%; raw schema or bbox may have changed"
    )
    assert rounded_pct >= 95, (
        f"coord_rounded_valid share={rounded_pct:.1f}% below 95%; raw schema "
        "or bbox may have changed"
    )

    # 6. Six-minute exceedance among recorded times within published-statistic sanity band.
    if rt.notna().any():
        exceed_pct = float(
            df.loc[df["response_time_seconds"].notna(), "exceeds_six_min_target"].mean()
            * 100
        )
        assert 10 <= exceed_pct <= 60, (
            f"exceeds_six_min_target share={exceed_pct:.1f}% outside sanity band "
            "10--60%; sanity check failed"
        )

    # 7. Incident-group composition stable.
    fa_pct = float(
        df["IncidentGroup"].eq("False Alarm").mean() * 100
    )
    assert 30 <= fa_pct <= 60, (
        f"False Alarm share={fa_pct:.1f}% outside sanity band 30--60%"
    )

    print("  all validation checks passed", flush=True)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    if not RAW_PATH.exists():
        print(f"ERROR: raw input not found at {RAW_PATH}", file=sys.stderr)
        return 2

    raw_sha = sha256_of(RAW_PATH)
    df_raw = load_raw(RAW_PATH)
    raw_rows = len(df_raw)

    df = add_derived_columns(df_raw)

    print(f"Writing {OUT_PARQUET.relative_to(PROJECT_ROOT)} ...", flush=True)
    df.to_parquet(OUT_PARQUET, index=False)
    print(f"  wrote {len(df):,} rows x {df.shape[1]} cols", flush=True)

    write_provenance(
        raw_path=RAW_PATH,
        raw_sha256=raw_sha,
        raw_rows=raw_rows,
        out_rows=len(df),
        out_cols=list(df.columns),
    )
    write_dictionary(df)
    write_dq_memo(df, raw_rows)

    validation_checks(df)

    print("Done.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
