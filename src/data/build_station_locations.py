"""
Build station responsibility-footprint proxy from the canonical LFB incidents parquet.

LFB does publish a `lfb_stations` open dataset on the London Datastore. Until
that release is integrated, this script derives a narrower *assignment-
footprint* proxy from the incident-resolution canonical dataset: for each unique value of
`IncidentStationGround` it takes the median (Easting_rounded, Northing_rounded)
of all incidents the station was the ground responsibility for, and converts
the OSGB36 metres into WGS84 latitude / longitude for the front end.

The derivation is honest about provenance: this is the centroid of where the
station's responsibility footprint sits, not the location of the brick-and-
mortar fire station building itself. It is suitable only for the §5.5
assignment-footprint scenario ("how do borough incident centroids relate to
historic station responsibility footprints if a named footprint is removed?").
It is not a station-coverage, routing, or relocation model; the recovery path
for those claims is to integrate the published station-locations release.
Bispo et al.'s r = 0.96 Euclidean vs road-network distance result
\\cite{reconfig2023} is used only to justify straight-line distances within
this explicitly bounded footprint proxy.

Input:  data/processed/lfb_canonical_2024_2026.parquet
Output: data/processed/lfb_station_locations_2024_2026.parquet
        data/processed/lfb_station_locations_2024_2026_provenance.json
        data/processed/lfb_station_locations_2024_2026_dictionary.md

Run from project root:
    python src/data/build_station_locations.py
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
OUT_PARQUET = OUT_DIR / "lfb_station_locations_2024_2026.parquet"
OUT_PROVENANCE = OUT_DIR / "lfb_station_locations_2024_2026_provenance.json"
OUT_DICTIONARY = OUT_DIR / "lfb_station_locations_2024_2026_dictionary.md"

# OSGB36 (EPSG:27700) -> WGS84 (EPSG:4326).
TRANSFORMER = pyproj.Transformer.from_crs("EPSG:27700", "EPSG:4326", always_xy=True)


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def derive_locations(canonical: pd.DataFrame) -> pd.DataFrame:
    # Drop rows missing the station ground responsibility (1 row in the
    # 2024-2026 slice) so the groupby does not produce a NaN station bucket.
    df = canonical.dropna(subset=["IncidentStationGround"]).copy()

    grouped = df.groupby("IncidentStationGround", observed=True)

    locations = grouped.agg(
        incident_count=("IncidentStationGround", "size"),
        easting_centroid_m=("Easting_rounded", "median"),
        northing_centroid_m=("Northing_rounded", "median"),
        # Spread of the responsibility footprint, in metres -- a station
        # whose incidents are tightly clustered has high IQR/2 < 1km, while
        # a station near a borough boundary may show wider spread.
        easting_iqr_m=(
            "Easting_rounded",
            lambda s: float(s.quantile(0.75) - s.quantile(0.25)),
        ),
        northing_iqr_m=(
            "Northing_rounded",
            lambda s: float(s.quantile(0.75) - s.quantile(0.25)),
        ),
    ).reset_index()

    locations = locations.rename(columns={"IncidentStationGround": "station_name"})

    # OSGB36 -> WGS84 conversion. pyproj returns (lon, lat) when always_xy=True.
    lons, lats = TRANSFORMER.transform(
        locations["easting_centroid_m"].to_numpy(),
        locations["northing_centroid_m"].to_numpy(),
    )
    locations["longitude"] = lons
    locations["latitude"] = lats

    # Round for stable parquet diffs / readable inspection.
    float_cols = locations.select_dtypes(include="float").columns
    locations[float_cols] = locations[float_cols].round(6)

    locations = locations.sort_values("station_name").reset_index(drop=True)
    return locations


def write_provenance(
    canonical_path: Path,
    canonical_sha256: str,
    canonical_rows: int,
    output_rows: int,
    columns: list[str],
) -> None:
    provenance = {
        "artefact": "lfb_station_locations_2024_2026",
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
            "station_output": output_rows,
        },
        "method": [
            "Derive each station's responsibility-footprint centroid as the (median Easting_rounded, median Northing_rounded) of all incidents grouped by IncidentStationGround.",
            "Convert OSGB36 (EPSG:27700) to WGS84 (EPSG:4326) via pyproj for D3-friendly latitude / longitude.",
            "Compute IQR of Easting_rounded and Northing_rounded as a cheap dispersion proxy for the station's responsibility footprint.",
        ],
        "honesty_note": (
            "The output is the centroid of each station's responsibility footprint, "
            "not the location of the brick-and-mortar fire station building. It is "
            "therefore an assignment-footprint proxy only: useful for comparing "
            "historic station-ground responsibility patterns, but not a station-"
            "coverage, routing, or relocation model."
        ),
        "output_columns": columns,
    }
    OUT_PROVENANCE.write_text(json.dumps(provenance, indent=2, ensure_ascii=False))
    print(f"  wrote {OUT_PROVENANCE.relative_to(PROJECT_ROOT)}", flush=True)


def write_dictionary(locations: pd.DataFrame) -> None:
    notes = {
        "station_name": "Distinct value of IncidentStationGround from the canonical LFB dataset (102 stations in the 2024-2026 slice).",
        "incident_count": "Number of incidents the station was ground responsibility for in the slice; used as a station-size context value.",
        "easting_centroid_m": "Median Easting_rounded of the station's incidents (OSGB36, metres).",
        "northing_centroid_m": "Median Northing_rounded of the station's incidents (OSGB36, metres).",
        "easting_iqr_m": "IQR of Easting_rounded across the station's incidents (metres). High IQR means the station's responsibility footprint is wide.",
        "northing_iqr_m": "Same as easting_iqr_m for the Northing axis.",
        "longitude": "WGS84 longitude of the median centroid (decimal degrees, EPSG:4326).",
        "latitude": "WGS84 latitude of the median centroid (decimal degrees, EPSG:4326).",
    }

    lines: list[str] = []
    lines.append("# LFB Station Locations Dictionary")
    lines.append("")
    lines.append("> Auto-generated by `src/data/build_station_locations.py`. Edit the script, not this file.")
    lines.append("")
    lines.append(f"- **Rows**: {len(locations):,}")
    lines.append(f"- **Columns**: {locations.shape[1]}")
    lines.append("")
    lines.append("## Columns")
    lines.append("")
    lines.append("| Column | Dtype | Notes |")
    lines.append("|---|---|---|")
    for col in locations.columns:
        lines.append(f"| `{col}` | {locations[col].dtype} | {notes.get(col, '')} |")
    lines.append("")

    OUT_DICTIONARY.write_text("\n".join(lines))
    print(f"  wrote {OUT_DICTIONARY.relative_to(PROJECT_ROOT)}", flush=True)


def validation_checks(locations: pd.DataFrame) -> None:
    print("Running validation checks ...", flush=True)

    # 1. 102 unique stations as recorded in the canonical (the 2024-2026 slice).
    assert len(locations) == 102, (
        f"expected 102 stations, got {len(locations)}; canonical schema may have changed"
    )

    # 2. Required columns present.
    required = {
        "station_name",
        "incident_count",
        "easting_centroid_m",
        "northing_centroid_m",
        "longitude",
        "latitude",
    }
    missing = required - set(locations.columns)
    assert not missing, f"missing required columns: {sorted(missing)}"

    # 3. All centroids inside the Greater London OSGB36 bbox used by the
    # canonical (build_canonical.py constants).
    assert locations["easting_centroid_m"].between(500_000, 565_000).all(), (
        "at least one station centroid Easting outside Greater London bbox"
    )
    assert locations["northing_centroid_m"].between(155_000, 210_000).all(), (
        "at least one station centroid Northing outside Greater London bbox"
    )

    # 4. WGS84 conversion roughly correct: London ~ (-0.5, 0.3) longitude,
    # (51.3, 51.7) latitude.
    assert locations["longitude"].between(-0.6, 0.4).all(), (
        f"longitude out of London band: min={locations['longitude'].min()}, "
        f"max={locations['longitude'].max()}"
    )
    assert locations["latitude"].between(51.2, 51.8).all(), (
        f"latitude out of London band: min={locations['latitude'].min()}, "
        f"max={locations['latitude'].max()}"
    )

    # 5. No duplicate station names.
    assert locations["station_name"].is_unique, "duplicate station names found"

    # 6. Per-station incident counts sum within tolerance of canonical row count
    # (less the rows dropped for missing IncidentStationGround).
    total = int(locations["incident_count"].sum())
    assert 290_000 <= total <= 295_000, (
        f"station incident_count sum {total:,} outside expected band 290-295k"
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

    locations = derive_locations(canonical)

    print(f"Writing {OUT_PARQUET.relative_to(PROJECT_ROOT)} ...", flush=True)
    locations.to_parquet(OUT_PARQUET, index=False)
    print(f"  wrote {len(locations):,} rows x {locations.shape[1]} cols", flush=True)

    write_provenance(
        canonical_path=CANONICAL_PATH,
        canonical_sha256=canonical_sha,
        canonical_rows=canonical_rows,
        output_rows=len(locations),
        columns=list(locations.columns),
    )
    write_dictionary(locations)

    validation_checks(locations)

    print("Done.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
