"""
Build borough-centroid proxy from the canonical LFB incidents parquet.

Mirrors `build_station_locations.py`: derives each borough's "where its
incidents happen" centroid by taking the median (Easting_rounded,
Northing_rounded) of all incidents grouped by `borough_canonical`. The
output is a 33-row parquet that the assignment-footprint API of §5.5 reads
together with `lfb_station_locations_2024_2026.parquet` to compute the
nearest open station responsibility footprint from each borough's incident centroid under a
user-supplied station-removal list.

The choice of *incident centroid* over *geographic centroid* is deliberate:
the footprint question is "where did incidents historically happen?" not
"where is the borough geometrically centred?". A borough whose incidents cluster
in one quadrant is correctly represented by that quadrant's centroid, not
by the polygonal middle of an unpopulated area.

Input:  data/processed/lfb_canonical_2024_2026.parquet
Output: data/processed/lfb_borough_centroids_2024_2026.parquet
        data/processed/lfb_borough_centroids_2024_2026_provenance.json
        data/processed/lfb_borough_centroids_2024_2026_dictionary.md

Run from project root:
    python src/data/build_borough_centroids.py
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import sys
from pathlib import Path

import pandas as pd
import pyproj

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CANONICAL_PATH = PROJECT_ROOT / "data" / "processed" / "lfb_canonical_2024_2026.parquet"
OUT_DIR = PROJECT_ROOT / "data" / "processed"
OUT_PARQUET = OUT_DIR / "lfb_borough_centroids_2024_2026.parquet"
OUT_PROVENANCE = OUT_DIR / "lfb_borough_centroids_2024_2026_provenance.json"
OUT_DICTIONARY = OUT_DIR / "lfb_borough_centroids_2024_2026_dictionary.md"

TRANSFORMER = pyproj.Transformer.from_crs("EPSG:27700", "EPSG:4326", always_xy=True)


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def derive_centroids(canonical: pd.DataFrame) -> pd.DataFrame:
    df = canonical.dropna(subset=["borough_canonical"]).copy()
    grouped = df.groupby("borough_canonical", observed=True)

    centroids = grouped.agg(
        incident_count=("borough_canonical", "size"),
        easting_centroid_m=("Easting_rounded", "median"),
        northing_centroid_m=("Northing_rounded", "median"),
    ).reset_index()

    lons, lats = TRANSFORMER.transform(
        centroids["easting_centroid_m"].to_numpy(),
        centroids["northing_centroid_m"].to_numpy(),
    )
    centroids["longitude"] = lons
    centroids["latitude"] = lats

    float_cols = centroids.select_dtypes(include="float").columns
    centroids[float_cols] = centroids[float_cols].round(6)

    return centroids.sort_values("borough_canonical").reset_index(drop=True)


def write_provenance(
    canonical_path: Path,
    canonical_sha256: str,
    canonical_rows: int,
    output_rows: int,
    columns: list[str],
) -> None:
    provenance = {
        "artefact": "lfb_borough_centroids_2024_2026",
        "schema_version": "1.0",
        "source": {
            "filename": canonical_path.name,
            "relative_path": str(canonical_path.relative_to(PROJECT_ROOT)),
            "sha256": canonical_sha256,
            "upstream_artefact": "lfb_canonical_2024_2026",
        },
        "build": {
            "extracted_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
            "script": str(Path(__file__).relative_to(PROJECT_ROOT)),
            "python_version": sys.version.split()[0],
            "pandas_version": pd.__version__,
            "pyproj_version": pyproj.__version__,
        },
        "row_counts": {
            "canonical_input": canonical_rows,
            "borough_output": output_rows,
        },
        "method": [
            "Group canonical by borough_canonical; take median (Easting_rounded, Northing_rounded) per group as the borough's incident centroid (OSGB36 metres).",
            "Convert OSGB36 to WGS84 via pyproj for D3 consumption.",
        ],
        "honesty_note": (
            "Output is the centroid of where incidents happen in each borough, "
            "not the borough's geographic centroid. It is used only as the borough "
            "anchor in the §5.5 assignment-footprint proxy, where it is compared "
            "with station responsibility-footprint centroids derived from the same "
            "canonical incident table."
        ),
        "output_columns": columns,
    }
    OUT_PROVENANCE.write_text(json.dumps(provenance, indent=2, ensure_ascii=False))
    print(f"  wrote {OUT_PROVENANCE.relative_to(PROJECT_ROOT)}", flush=True)


def write_dictionary(centroids: pd.DataFrame) -> None:
    notes = {
        "borough_canonical": "Title-cased borough name from the canonical dataset (33 boroughs in the 2024-2026 slice).",
        "incident_count": "Number of incidents in the borough across the slice.",
        "easting_centroid_m": "Median Easting_rounded of the borough's incidents (OSGB36, metres).",
        "northing_centroid_m": "Median Northing_rounded of the borough's incidents (OSGB36, metres).",
        "longitude": "WGS84 longitude of the median centroid (decimal degrees, EPSG:4326).",
        "latitude": "WGS84 latitude of the median centroid (decimal degrees, EPSG:4326).",
    }
    lines: list[str] = []
    lines.append("# LFB Borough Centroids Dictionary")
    lines.append("")
    lines.append("> Auto-generated by `src/data/build_borough_centroids.py`. Edit the script, not this file.")
    lines.append("")
    lines.append(f"- **Rows**: {len(centroids):,}")
    lines.append(f"- **Columns**: {centroids.shape[1]}")
    lines.append("")
    lines.append("## Columns")
    lines.append("")
    lines.append("| Column | Dtype | Notes |")
    lines.append("|---|---|---|")
    for col in centroids.columns:
        lines.append(f"| `{col}` | {centroids[col].dtype} | {notes.get(col, '')} |")
    lines.append("")
    OUT_DICTIONARY.write_text("\n".join(lines))
    print(f"  wrote {OUT_DICTIONARY.relative_to(PROJECT_ROOT)}", flush=True)


def validation_checks(centroids: pd.DataFrame) -> None:
    print("Running validation checks ...", flush=True)
    assert len(centroids) == 33, f"expected 33 boroughs, got {len(centroids)}"
    required = {
        "borough_canonical",
        "incident_count",
        "easting_centroid_m",
        "northing_centroid_m",
        "longitude",
        "latitude",
    }
    missing = required - set(centroids.columns)
    assert not missing, f"missing columns: {sorted(missing)}"
    assert centroids["borough_canonical"].is_unique, "duplicate borough names"
    assert centroids["easting_centroid_m"].between(500_000, 565_000).all()
    assert centroids["northing_centroid_m"].between(155_000, 210_000).all()
    assert centroids["longitude"].between(-0.6, 0.4).all()
    assert centroids["latitude"].between(51.2, 51.8).all()
    print("  all validation checks passed", flush=True)


def main() -> int:
    if not CANONICAL_PATH.exists():
        print(f"ERROR: canonical input not found at {CANONICAL_PATH}", file=sys.stderr)
        return 2

    canonical_sha = sha256_of(CANONICAL_PATH)
    print(f"Reading {CANONICAL_PATH.relative_to(PROJECT_ROOT)} ...", flush=True)
    canonical = pd.read_parquet(CANONICAL_PATH)
    canonical_rows = len(canonical)
    print(f"  loaded {canonical_rows:,} rows", flush=True)

    centroids = derive_centroids(canonical)

    print(f"Writing {OUT_PARQUET.relative_to(PROJECT_ROOT)} ...", flush=True)
    centroids.to_parquet(OUT_PARQUET, index=False)
    print(f"  wrote {len(centroids):,} rows x {centroids.shape[1]} cols", flush=True)

    write_provenance(
        canonical_path=CANONICAL_PATH,
        canonical_sha256=canonical_sha,
        canonical_rows=canonical_rows,
        output_rows=len(centroids),
        columns=list(centroids.columns),
    )
    write_dictionary(centroids)
    validation_checks(centroids)

    print("Done.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
