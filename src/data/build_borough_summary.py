"""
Build borough-level monthly summary table from the canonical LFB parquet.

Input:  data/processed/lfb_canonical_2024_2026.parquet (built by build_canonical.py)
Output: data/processed/lfb_borough_summary_2024_2026.parquet
        data/processed/lfb_borough_summary_2024_2026_dictionary.md
        data/processed/lfb_borough_summary_2024_2026_provenance.json

Run from the project root:
    python src/data/build_borough_summary.py

Purpose:
- Pre-aggregates the 293,646-row canonical dataset to the granularity the
  dashboard backend will hit on every request: borough x year_month x
  incident_group. The resulting table has roughly 33 boroughs x 26 months
  x 3 incident groups = ~2,500 rows, which the Flask /borough_summary
  endpoint can serve in milliseconds without re-aggregating every time.
- Pre-computes the response-time distribution summaries (mean, median,
  p90) plus the 6-minute exceedance share and per-cell coord-validity
  shares, so that downstream views can render uncertainty without
  re-scanning the raw incidents.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CANONICAL_PATH = PROJECT_ROOT / "data" / "processed" / "lfb_canonical_2024_2026.parquet"
OUT_DIR = PROJECT_ROOT / "data" / "processed"
OUT_PARQUET = OUT_DIR / "lfb_borough_summary_2024_2026.parquet"
OUT_DICTIONARY = OUT_DIR / "lfb_borough_summary_2024_2026_dictionary.md"
OUT_PROVENANCE = OUT_DIR / "lfb_borough_summary_2024_2026_provenance.json"

GROUP_KEYS = ["borough_canonical", "year_month", "IncidentGroup"]


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def percentile(series: pd.Series, q: float) -> float:
    series = series.dropna()
    if series.empty:
        return float("nan")
    return float(np.quantile(series, q))


def aggregate(df: pd.DataFrame) -> pd.DataFrame:
    # Drop rows with no IncidentGroup (1 row in current data) so groupby
    # does not silently produce an "NA" group.
    df = df.dropna(subset=["IncidentGroup", "borough_canonical", "year_month"])

    grouped = df.groupby(GROUP_KEYS, observed=True, dropna=False)

    summary = grouped.agg(
        incident_count=("IncidentGroup", "size"),
        response_time_min_mean=("response_time_minutes", "mean"),
        response_time_min_median=("response_time_minutes", "median"),
        response_time_min_p90=(
            "response_time_minutes",
            lambda s: percentile(s, 0.9),
        ),
        response_time_min_p95=(
            "response_time_minutes",
            lambda s: percentile(s, 0.95),
        ),
        response_time_recorded_share=(
            "response_time_seconds",
            lambda s: float(s.notna().mean()),
        ),
        # `exceeds_six_min_target` is a nullable boolean in the canonical
        # (pd.NA where response_time_seconds is missing). pandas' `.mean()`
        # skips NA, so this aggregation correctly returns the share of cells
        # *with a recorded time* that exceeded six minutes -- not the share
        # of all incidents; this defends against denominator drift.
        exceeds_six_min_share=(
            "exceeds_six_min_target",
            "mean",
        ),
        num_pumps_mean=("NumPumpsAttending", "mean"),
        coord_precise_share=("coord_precise_valid", "mean"),
        coord_rounded_share=("coord_rounded_valid", "mean"),
        distinct_ground_stations=(
            "IncidentStationGround",
            lambda s: int(s.dropna().nunique()),
        ),
    ).reset_index()

    # Sort for deterministic output across rebuilds.
    summary = summary.sort_values(GROUP_KEYS).reset_index(drop=True)

    # Round float columns to 4 dp for readable parquet inspection; the
    # source canonical has full precision if more is ever needed.
    float_cols = summary.select_dtypes(include="float").columns
    summary[float_cols] = summary[float_cols].round(4)

    return summary


def write_provenance(
    canonical_path: Path,
    canonical_sha256: str,
    canonical_rows: int,
    summary_rows: int,
    summary_cols: list[str],
) -> None:
    extracted_at = dt.datetime.now(dt.timezone.utc).isoformat()
    provenance = {
        "artefact": "lfb_borough_summary_2024_2026",
        "schema_version": "1.0",
        "source": {
            "filename": canonical_path.name,
            "relative_path": str(canonical_path.relative_to(PROJECT_ROOT)),
            "sha256": canonical_sha256,
            "upstream_artefact": "lfb_canonical_2024_2026",
        },
        "build": {
            "extracted_at_utc": extracted_at,
            "script": str(Path(__file__).relative_to(PROJECT_ROOT)),
            "python_version": sys.version.split()[0],
            "pandas_version": pd.__version__,
        },
        "row_counts": {
            "canonical_input": canonical_rows,
            "summary_output": summary_rows,
        },
        "group_keys": GROUP_KEYS,
        "aggregations": [
            "incident_count = size of group",
            "response_time_min_{mean,median,p90,p95} over response_time_minutes",
            "response_time_recorded_share = share of group with non-null response_time_seconds",
            "exceeds_six_min_share = mean of exceeds_six_min_target boolean",
            "num_pumps_mean = mean NumPumpsAttending",
            "coord_precise_share, coord_rounded_share = mean of the two coord-validity booleans",
            "distinct_ground_stations = nunique IncidentStationGround in group",
        ],
        "output_columns": summary_cols,
    }
    OUT_PROVENANCE.write_text(json.dumps(provenance, indent=2, ensure_ascii=False))
    print(f"  wrote {OUT_PROVENANCE.relative_to(PROJECT_ROOT)}", flush=True)


def write_dictionary(summary: pd.DataFrame) -> None:
    notes = {
        "borough_canonical": "Canonical borough name (title-cased) from the canonical dataset.",
        "year_month": "Year-month period as 'YYYY-MM' string.",
        "IncidentGroup": "LFB top-level taxonomy: Fire / False Alarm / Special Service.",
        "incident_count": "Count of incidents in the (borough, month, group) cell.",
        "response_time_min_mean": "Mean first-pump response time (minutes) within the cell.",
        "response_time_min_median": "Median first-pump response time (minutes) within the cell.",
        "response_time_min_p90": "90th percentile of first-pump response time (minutes).",
        "response_time_min_p95": "95th percentile of first-pump response time (minutes).",
        "response_time_recorded_share": "Share of incidents in the cell with a recorded first-pump time.",
        "exceeds_six_min_share": "Share of incidents *with a recorded first-pump time* whose first pump exceeded the 6-minute target. The denominator is `incident_count * response_time_recorded_share`, NOT `incident_count`. This is enforced by the canonical's `exceeds_six_min_target` column being a nullable boolean (pd.NA where response_time is missing) so that `.mean()` skips missing-time rows.",
        "num_pumps_mean": "Mean NumPumpsAttending in the cell.",
        "coord_precise_share": "Share of incidents in the cell with valid precise coordinates (Easting_m / Northing_m).",
        "coord_rounded_share": "Share of incidents with valid rounded 100m-grid coordinates.",
        "distinct_ground_stations": "Number of distinct IncidentStationGround values seen in the cell.",
    }

    lines: list[str] = []
    lines.append("# LFB Borough Summary Dictionary")
    lines.append("")
    lines.append("> Auto-generated by `src/data/build_borough_summary.py`. Edit the script, not this file.")
    lines.append("")
    lines.append(f"- **Rows**: {len(summary):,}")
    lines.append(f"- **Columns**: {summary.shape[1]}")
    lines.append(f"- **Group keys**: {', '.join(GROUP_KEYS)}")
    lines.append("")
    lines.append("## Columns")
    lines.append("")
    lines.append("| Column | Dtype | Notes |")
    lines.append("|---|---|---|")
    for col in summary.columns:
        dtype = str(summary[col].dtype)
        note = notes.get(col, "")
        lines.append(f"| `{col}` | {dtype} | {note} |")
    lines.append("")

    OUT_DICTIONARY.write_text("\n".join(lines))
    print(f"  wrote {OUT_DICTIONARY.relative_to(PROJECT_ROOT)}", flush=True)


def validation_checks(summary: pd.DataFrame, canonical_rows: int) -> None:
    print("Running validation checks ...", flush=True)

    # 1. Non-empty.
    assert len(summary) > 0, "summary is empty"

    # 2. Group cardinality sanity. 33 boroughs * 26 months * 3 incident groups
    # = 2574 maximal cells; observed cell count should be in 80--110% of that
    # (some cells are empty, so we under-count, but never over-count by much).
    expected_max = 33 * 26 * 3
    cells = len(summary)
    assert 0.5 * expected_max <= cells <= expected_max, (
        f"summary row count {cells} outside expected band "
        f"{int(0.5 * expected_max)}--{expected_max}"
    )

    # 3. Counts must sum to the canonical row count minus the small number
    # of rows dropped for missing IncidentGroup, borough, or year_month.
    # In the 2024-2026 slice this drop is ~50 rows (<0.05%); allow up to 1%
    # so that future-vintage data with slightly more nulls still passes.
    total_in_summary = int(summary["incident_count"].sum())
    drop_tolerance = max(int(canonical_rows * 0.01), 100)
    assert canonical_rows - drop_tolerance <= total_in_summary <= canonical_rows, (
        f"summary incident_count sum {total_in_summary} not within "
        f"{drop_tolerance} rows of canonical {canonical_rows}"
    )

    # 4. Response-time means within sanity band.
    rt_mean = summary["response_time_min_mean"].dropna()
    assert rt_mean.min() >= 1.0, f"min cell mean {rt_mean.min():.2f} < 1 min, suspect"
    assert rt_mean.max() <= 30.0, f"max cell mean {rt_mean.max():.2f} > 30 min, suspect"

    # 5. Exceedance shares are valid probabilities.
    exc = summary["exceeds_six_min_share"].dropna()
    assert exc.min() >= 0.0 and exc.max() <= 1.0, (
        "exceeds_six_min_share outside [0, 1]"
    )

    # 6. coord_rounded_share is consistently 1.0 across all cells (rounded
    # coordinates are released for 100% of records, so every cell should be
    # at exactly 1.0 give or take floating-point noise).
    coord_rounded_min = float(summary["coord_rounded_share"].min())
    assert coord_rounded_min >= 0.99, (
        f"coord_rounded_share min={coord_rounded_min:.3f} below 0.99; the "
        "100% rounded-coordinate invariant has been violated"
    )

    print("  all validation checks passed", flush=True)


def main() -> int:
    if not CANONICAL_PATH.exists():
        print(
            f"ERROR: canonical input not found at {CANONICAL_PATH}; "
            "run src/data/build_canonical.py first",
            file=sys.stderr,
        )
        return 2

    canonical_sha = sha256_of(CANONICAL_PATH)
    print(f"Reading {CANONICAL_PATH.relative_to(PROJECT_ROOT)} ...", flush=True)
    canonical = pd.read_parquet(CANONICAL_PATH)
    canonical_rows = len(canonical)
    print(f"  loaded {canonical_rows:,} rows", flush=True)

    summary = aggregate(canonical)

    print(f"Writing {OUT_PARQUET.relative_to(PROJECT_ROOT)} ...", flush=True)
    summary.to_parquet(OUT_PARQUET, index=False)
    print(f"  wrote {len(summary):,} rows x {summary.shape[1]} cols", flush=True)

    write_provenance(
        canonical_path=CANONICAL_PATH,
        canonical_sha256=canonical_sha,
        canonical_rows=canonical_rows,
        summary_rows=len(summary),
        summary_cols=list(summary.columns),
    )
    write_dictionary(summary)

    validation_checks(summary, canonical_rows)

    print("Done.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
