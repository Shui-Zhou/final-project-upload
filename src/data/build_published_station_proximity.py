"""
Build D1 recovery artefacts from a public LFB fire-station address table.

The source is the London Datastore "Low Carbon Generators" dataset, whose
LFEPA/LFB rows list fire stations, addresses, and postcodes. It is not a live
operational station master list, so this script uses it only for report-side
straight-line proximity/accessibility evidence. It does not create a routing,
coverage, dispatch, relocation, or optimisation model.

Geocoding is performed through postcodes.io. A few obvious postcode/station-name
typos in the public CSV are corrected explicitly and recorded in provenance.

Outputs:
  data/processed/lfb_published_station_locations_2026.parquet
  data/processed/lfb_published_station_locations_2026_{dictionary,dq_memo}.md
  data/processed/lfb_published_station_locations_2026_provenance.json
  data/processed/lfb_station_d1_comparison_2024_2026.parquet
  data/processed/lfb_station_d1_comparison_2024_2026_{dictionary,dq_memo}.md
  data/processed/lfb_borough_station_proximity_2024_2026.parquet
  data/processed/lfb_borough_station_proximity_2024_2026_{dictionary,dq_memo}.md
  report/Final Report Latex Template (Data Science)/figures/station_proximity/*.png
"""

from __future__ import annotations

import datetime as dt
import hashlib
import io
import json
import re
import sys
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import pandas as pd
import pyproj
import requests

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = PROJECT_ROOT / "data" / "raw"
OUT_DIR = PROJECT_ROOT / "data" / "processed"
FIG_DIR = (
    PROJECT_ROOT
    / "report"
    / "Final Report Latex Template (Data Science)"
    / "figures"
    / "station_proximity"
)

SOURCE_URL = (
    "https://data.london.gov.uk/download/2jkzj/"
    "7f069dca-8c18-405a-9dc4-0d6f802d52a5/"
    "LFB%20low%20carbon%20generators%20at%20fire%20stations%20-%20June%202017.csv"
)
SOURCE_PAGE = "https://data.london.gov.uk/dataset/low-carbon-generators-2jkzj"
RAW_CSV = RAW_DIR / "LFB_low_carbon_generators_at_fire_stations_June_2017.csv"

PUBLISHED_PARQUET = OUT_DIR / "lfb_published_station_locations_2026.parquet"
PUBLISHED_PROVENANCE = OUT_DIR / "lfb_published_station_locations_2026_provenance.json"
PUBLISHED_DICTIONARY = OUT_DIR / "lfb_published_station_locations_2026_dictionary.md"
PUBLISHED_DQ_MEMO = OUT_DIR / "lfb_published_station_locations_2026_dq_memo.md"

COMPARISON_PARQUET = OUT_DIR / "lfb_station_d1_comparison_2024_2026.parquet"
COMPARISON_DICTIONARY = OUT_DIR / "lfb_station_d1_comparison_2024_2026_dictionary.md"
COMPARISON_DQ_MEMO = OUT_DIR / "lfb_station_d1_comparison_2024_2026_dq_memo.md"

BOROUGH_PROXIMITY_PARQUET = OUT_DIR / "lfb_borough_station_proximity_2024_2026.parquet"
BOROUGH_PROXIMITY_DICTIONARY = (
    OUT_DIR / "lfb_borough_station_proximity_2024_2026_dictionary.md"
)
BOROUGH_PROXIMITY_DQ_MEMO = (
    OUT_DIR / "lfb_borough_station_proximity_2024_2026_dq_memo.md"
)

DERIVED_STATIONS = OUT_DIR / "lfb_station_locations_2024_2026.parquet"
BOROUGH_CENTROIDS = OUT_DIR / "lfb_borough_centroids_2024_2026.parquet"

# Official CSV issues found during D1 recovery. Values are verified against
# LFB borough pages / public postcode references where postcodes.io rejected
# the CSV value. The original values are retained in `postcode_raw`.
POSTCODE_CORRECTIONS = {
    "Chelsea": "SW3 5UF",  # CSV has SW1 5UF.
    "Deptford": "SE8 5DB",  # CSV has SE8 8PR.
    "Lambeth": "SE1 7SP",  # CSV has SE1 7SD.
    "Lambeth River": "SE1 7SP",  # shares the Albert Embankment site.
}

STATION_NAME_CORRECTIONS = {
    "Eltam": "Eltham",
    "Hornchuch": "Hornchurch",
    "Northholt": "Northolt",
}

TRANSFORMER_TO_WGS84 = pyproj.Transformer.from_crs(
    "EPSG:27700", "EPSG:4326", always_xy=True
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def normalise_station_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value).lower().replace("&", "and"))


def download_source() -> bytes:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    response = requests.get(
        SOURCE_URL,
        headers={"User-Agent": "Mozilla/5.0 LFB station proximity build script"},
        timeout=30,
    )
    response.raise_for_status()
    RAW_CSV.write_bytes(response.content)
    return response.content


def geocode_postcode(postcode: str) -> dict[str, Any] | None:
    compact = re.sub(r"\s+", "", postcode.upper())
    for endpoint in ("postcodes", "terminated_postcodes"):
        url = f"https://api.postcodes.io/{endpoint}/{compact}"
        response = requests.get(url, timeout=15)
        if response.status_code == 200:
            return response.json()["result"]
    return None


def build_published_stations(raw_csv: bytes) -> pd.DataFrame:
    raw = pd.read_csv(io.BytesIO(raw_csv))
    keep = raw[["Fire station", "Address", "Postcode"]].copy()
    keep = keep.rename(
        columns={
            "Fire station": "station_name_raw",
            "Address": "address",
            "Postcode": "postcode_raw",
        }
    )
    keep["station_name"] = keep["station_name_raw"].replace(STATION_NAME_CORRECTIONS)
    keep["postcode"] = keep.apply(
        lambda row: POSTCODE_CORRECTIONS.get(row["station_name_raw"], row["postcode_raw"]),
        axis=1,
    )
    keep["station_name_key"] = keep["station_name"].map(normalise_station_name)

    geocoded_rows: list[dict[str, Any]] = []
    for row in keep.to_dict("records"):
        result = geocode_postcode(str(row["postcode"]))
        if result is None:
            raise RuntimeError(
                f"postcodes.io could not geocode {row['station_name']} "
                f"postcode {row['postcode']}"
            )
        geocoded_rows.append(
            {
                **row,
                "postcode_geocoded": result["postcode"],
                "postcode_status": "terminated"
                if "year_terminated" in result
                else "live",
                "easting_m": result["eastings"],
                "northing_m": result["northings"],
                "longitude": result["longitude"],
                "latitude": result["latitude"],
                "admin_district": result.get("admin_district"),
            }
        )

    stations = pd.DataFrame(geocoded_rows)
    stations = stations.sort_values("station_name").reset_index(drop=True)
    float_cols = ["longitude", "latitude"]
    stations[float_cols] = stations[float_cols].round(6)
    return stations


def build_station_comparison(published: pd.DataFrame) -> pd.DataFrame:
    derived = pd.read_parquet(DERIVED_STATIONS)
    derived = derived.assign(
        station_name_key=derived["station_name"].map(normalise_station_name)
    )
    comp = published.merge(
        derived,
        on="station_name_key",
        how="left",
        suffixes=("_published", "_derived"),
    )
    comp["matched_to_derived_footprint"] = comp["station_name_derived"].notna()
    comp["published_vs_derived_distance_m"] = (
        (
            comp["easting_m"].astype(float) - comp["easting_centroid_m"].astype(float)
        )
        ** 2
        + (
            comp["northing_m"].astype(float) - comp["northing_centroid_m"].astype(float)
        )
        ** 2
    ) ** 0.5
    comp["published_vs_derived_distance_km"] = (
        comp["published_vs_derived_distance_m"] / 1000
    ).round(3)
    return comp.sort_values(
        ["matched_to_derived_footprint", "published_vs_derived_distance_km"],
        ascending=[True, False],
    ).reset_index(drop=True)


def build_borough_proximity(published: pd.DataFrame) -> pd.DataFrame:
    boroughs = pd.read_parquet(BOROUGH_CENTROIDS)
    pub = published[published["station_name"] != "Merton"].copy()

    rows: list[dict[str, Any]] = []
    for borough in boroughs.to_dict("records"):
        distances = (
            (
                pub["easting_m"].astype(float)
                - float(borough["easting_centroid_m"])
            )
            ** 2
            + (
                pub["northing_m"].astype(float)
                - float(borough["northing_centroid_m"])
            )
            ** 2
        ) ** 0.5
        nearest_idx = distances.idxmin()
        nearest = pub.loc[nearest_idx]
        rows.append(
            {
                "borough_canonical": borough["borough_canonical"],
                "incident_count": int(borough["incident_count"]),
                "borough_easting_centroid_m": float(borough["easting_centroid_m"]),
                "borough_northing_centroid_m": float(borough["northing_centroid_m"]),
                "nearest_station_name": nearest["station_name"],
                "nearest_station_postcode": nearest["postcode_geocoded"],
                "nearest_station_distance_m": float(distances.loc[nearest_idx]),
                "nearest_station_distance_km": round(float(distances.loc[nearest_idx]) / 1000, 3),
            }
        )
    return pd.DataFrame(rows).sort_values(
        "nearest_station_distance_km", ascending=False
    ).reset_index(drop=True)


def write_dictionary(path: Path, df: pd.DataFrame, notes: dict[str, str], title: str) -> None:
    lines = [
        f"# {title}",
        "",
        "> Auto-generated by `src/data/build_published_station_proximity.py`. Edit the script, not this file.",
        "",
        f"- **Rows**: {len(df):,}",
        f"- **Columns**: {df.shape[1]}",
        "",
        "## Columns",
        "",
        "| Column | Dtype | Notes |",
        "|---|---|---|",
    ]
    for col in df.columns:
        lines.append(f"| `{col}` | {df[col].dtype} | {notes.get(col, '')} |")
    path.write_text("\n".join(lines) + "\n")


def write_memos(
    published: pd.DataFrame, comparison: pd.DataFrame, borough_proximity: pd.DataFrame
) -> None:
    unmatched = comparison[~comparison["matched_to_derived_footprint"]]
    matched = comparison[comparison["matched_to_derived_footprint"]]
    top_shift = matched.nlargest(10, "published_vs_derived_distance_km")
    top_boroughs = borough_proximity.nlargest(10, "nearest_station_distance_km")

    PUBLISHED_DQ_MEMO.write_text(
        "\n".join(
            [
                "# Published Station Locations DQ Memo",
                "",
                "> Auto-generated by `src/data/build_published_station_proximity.py`.",
                "",
                "## Source and Scope",
                "",
                f"- Source page: {SOURCE_PAGE}",
                f"- Source CSV: {SOURCE_URL}",
                "- The London Datastore page describes the LFEPA/LFB portion as details of low-carbon generators located at fire stations, with fire-station locations including postcode.",
                "- This artefact uses the table as a public station-address list and geocodes postcodes through postcodes.io.",
                "- It is **not** a routing-grade station entrance dataset and must not be described as coverage, dispatch, relocation, or optimisation evidence.",
                "",
                "## Counts",
                "",
                f"- Published rows: {len(published):,}",
                f"- Unique station names after typo correction: {published['station_name'].nunique():,}",
                f"- Live postcodes: {(published['postcode_status'] == 'live').sum():,}",
                f"- Terminated postcodes retained by postcodes.io: {(published['postcode_status'] == 'terminated').sum():,}",
                "",
                "## Explicit Corrections",
                "",
                f"- Station-name corrections: `{STATION_NAME_CORRECTIONS}`.",
                f"- Postcode corrections: `{POSTCODE_CORRECTIONS}`.",
                "",
            ]
        )
    )

    COMPARISON_DQ_MEMO.write_text(
        "\n".join(
            [
                "# Station D1 Comparison Memo",
                "",
                "> Auto-generated by `src/data/build_published_station_proximity.py`.",
                "",
                "## Interpretation",
                "",
                "This table compares public postcode-geocoded station addresses with the earlier assignment-footprint centroids derived from `IncidentStationGround` incidents. Large distances do not mean either table is wrong: they quantify why the derived footprint centroid should not be presented as a building location.",
                "",
                "## Counts",
                "",
                f"- Published rows: {len(comparison):,}",
                f"- Rows matched to derived assignment-footprint station names: {int(comparison['matched_to_derived_footprint'].sum()):,}",
                f"- Rows not matched to derived names: {len(unmatched):,} ({', '.join(unmatched['station_name_published'].astype(str))})",
                f"- Median matched published-vs-derived shift: {matched['published_vs_derived_distance_km'].median():.2f} km",
                f"- 90th percentile matched shift: {matched['published_vs_derived_distance_km'].quantile(0.9):.2f} km",
                "",
                "## Largest Published-vs-Derived Shifts",
                "",
                "| Station | Shift km |",
                "|---|---:|",
                *[
                    f"| {row.station_name_published} | {row.published_vs_derived_distance_km:.2f} |"
                    for row in top_shift.itertuples()
                ],
                "",
            ]
        )
    )

    BOROUGH_PROXIMITY_DQ_MEMO.write_text(
        "\n".join(
            [
                "# Borough Station Proximity Memo",
                "",
                "> Auto-generated by `src/data/build_published_station_proximity.py`.",
                "",
                "## Interpretation",
                "",
                "Each borough is represented by its incident-demand centroid from the existing borough-centroid artefact. The nearest-station distance is a straight-line proximity cue from that demand centroid to the nearest public station postcode coordinate. It is suitable for report-side triage/accessibility context only.",
                "",
                "## Counts",
                "",
                f"- Borough rows: {len(borough_proximity):,}",
                f"- Median nearest-station distance: {borough_proximity['nearest_station_distance_km'].median():.2f} km",
                f"- Largest nearest-station distance: {borough_proximity['nearest_station_distance_km'].max():.2f} km",
                "",
                "## Highest Distance Boroughs",
                "",
                "| Borough | Nearest station | Distance km | Incidents |",
                "|---|---|---:|---:|",
                *[
                    f"| {row.borough_canonical} | {row.nearest_station_name} | {row.nearest_station_distance_km:.2f} | {row.incident_count:,} |"
                    for row in top_boroughs.itertuples()
                ],
                "",
            ]
        )
    )


def write_provenance(raw_sha: str, published: pd.DataFrame) -> None:
    provenance = {
        "artefact": "lfb_published_station_locations_2026",
        "schema_version": "1.0",
        "source": {
            "page": SOURCE_PAGE,
            "csv_url": SOURCE_URL,
            "raw_relative_path": str(RAW_CSV.relative_to(PROJECT_ROOT)),
            "raw_sha256": raw_sha,
            "licence": "Open Government Licence v2, per London Datastore page",
            "source_limit": (
                "The table is a low-carbon generators dataset that includes "
                "LFEPA/LFB fire-station addresses and postcodes. It is used "
                "as a public address list, not as a live operational station "
                "master list."
            ),
        },
        "geocoder": {
            "service": "postcodes.io",
            "method": "postcode centroid lookup; terminated_postcodes alternate lookup for retired postcodes",
            "postcode_corrections": POSTCODE_CORRECTIONS,
            "station_name_corrections": STATION_NAME_CORRECTIONS,
        },
        "build": {
            "extracted_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
            "script": str(Path(__file__).relative_to(PROJECT_ROOT)),
            "python_version": sys.version.split()[0],
            "pandas_version": pd.__version__,
            "pyproj_version": pyproj.__version__,
            "requests_version": requests.__version__,
        },
        "row_counts": {
            "published_station_rows": int(len(published)),
            "unique_station_names": int(published["station_name"].nunique()),
            "live_postcodes": int((published["postcode_status"] == "live").sum()),
            "terminated_postcodes": int(
                (published["postcode_status"] == "terminated").sum()
            ),
        },
        "honesty_note": (
            "Use as straight-line proximity/accessibility context only. Do not "
            "describe as coverage, routing-grade travel time, dispatch, "
            "relocation, or optimisation evidence."
        ),
    }
    PUBLISHED_PROVENANCE.write_text(json.dumps(provenance, indent=2, ensure_ascii=False))


def plot_figures(comparison: pd.DataFrame, borough_proximity: pd.DataFrame) -> None:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    plt.style.use("seaborn-v0_8-whitegrid")

    matched = comparison[comparison["matched_to_derived_footprint"]].nlargest(
        15, "published_vs_derived_distance_km"
    )
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.barh(
        matched["station_name_published"],
        matched["published_vs_derived_distance_km"],
        color="#0f766e",
    )
    ax.invert_yaxis()
    ax.set_xlabel("Distance between public station postcode and derived footprint centroid (km)")
    ax.set_ylabel("")
    ax.set_title(
        "Largest differences between public station locations and assignment-footprint centroids",
        pad=18,
    )
    fig.subplots_adjust(top=0.84)
    fig.text(
        0.125,
        0.885,
        "Straight-line distance; not routing or coverage evidence.",
        fontsize=9,
        color="#475569",
    )
    fig.tight_layout(rect=[0, 0, 1, 0.86])
    fig.savefig(FIG_DIR / "fig_station_d1_anchor_shift_top15.png", dpi=220)
    plt.close(fig)

    top = borough_proximity.nlargest(15, "nearest_station_distance_km")
    fig, ax = plt.subplots(figsize=(9, 5))
    colors = ["#dc2626" if x >= 3 else "#ea580c" if x >= 2 else "#0f766e" for x in top["nearest_station_distance_km"]]
    ax.barh(top["borough_canonical"], top["nearest_station_distance_km"], color=colors)
    ax.invert_yaxis()
    ax.set_xlabel("Nearest public station postcode from borough demand centroid (km)")
    ax.set_ylabel("")
    ax.set_title(
        "Borough demand-centroid proximity to nearest public station location",
        pad=18,
    )
    fig.subplots_adjust(top=0.84)
    fig.text(
        0.125,
        0.885,
        "Straight-line proximity from incident-demand centroid; not a station-placement recommendation.",
        fontsize=9,
        color="#475569",
    )
    fig.tight_layout(rect=[0, 0, 1, 0.86])
    fig.savefig(FIG_DIR / "fig_borough_nearest_station_proximity.png", dpi=220)
    plt.close(fig)


def validation_checks(
    published: pd.DataFrame, comparison: pd.DataFrame, borough_proximity: pd.DataFrame
) -> None:
    assert len(published) == 104, f"expected 104 published rows, got {len(published)}"
    assert published["station_name"].nunique() == 104
    assert published["postcode_geocoded"].notna().all()
    assert published["easting_m"].between(500_000, 565_000).all()
    assert published["northing_m"].between(155_000, 210_000).all()
    assert len(comparison) == 104
    assert int(comparison["matched_to_derived_footprint"].sum()) == 102
    unmatched = set(
        comparison.loc[
            ~comparison["matched_to_derived_footprint"], "station_name_published"
        ]
    )
    assert unmatched == {"Lambeth River", "Merton"}
    assert comparison.loc[
        comparison["matched_to_derived_footprint"],
        "published_vs_derived_distance_km",
    ].notna().all()
    assert len(borough_proximity) == 33
    assert (borough_proximity["nearest_station_distance_km"] >= 0).all()


def main() -> int:
    print("Downloading published station-address table ...", flush=True)
    raw_csv = download_source()
    raw_sha = sha256_bytes(raw_csv)
    print(f"  wrote {RAW_CSV.relative_to(PROJECT_ROOT)}", flush=True)

    published = build_published_stations(raw_csv)
    comparison = build_station_comparison(published)
    borough_proximity = build_borough_proximity(published)

    validation_checks(published, comparison, borough_proximity)

    published.to_parquet(PUBLISHED_PARQUET, index=False)
    comparison.to_parquet(COMPARISON_PARQUET, index=False)
    borough_proximity.to_parquet(BOROUGH_PROXIMITY_PARQUET, index=False)

    write_dictionary(
        PUBLISHED_DICTIONARY,
        published,
        {
            "station_name_raw": "Station name exactly as published in the source CSV.",
            "station_name": "Station name after explicit typo corrections.",
            "postcode_raw": "Postcode exactly as published in the source CSV.",
            "postcode": "Postcode after explicit corrections before geocoding.",
            "postcode_geocoded": "Canonical postcode returned by postcodes.io.",
            "postcode_status": "live or terminated according to postcodes.io lookup.",
            "easting_m": "OSGB36 easting from postcodes.io postcode centroid.",
            "northing_m": "OSGB36 northing from postcodes.io postcode centroid.",
            "longitude": "WGS84 longitude from postcodes.io.",
            "latitude": "WGS84 latitude from postcodes.io.",
        },
        "Published Station Locations Dictionary",
    )
    write_dictionary(
        COMPARISON_DICTIONARY,
        comparison,
        {
            "matched_to_derived_footprint": "Whether the public station name matches the existing IncidentStationGround-derived station-footprint artefact.",
            "published_vs_derived_distance_km": "Straight-line distance between public station postcode coordinate and derived assignment-footprint centroid.",
        },
        "Station D1 Comparison Dictionary",
    )
    write_dictionary(
        BOROUGH_PROXIMITY_DICTIONARY,
        borough_proximity,
        {
            "borough_canonical": "Canonical borough/local-authority name.",
            "incident_count": "Incident count represented by the borough demand centroid.",
            "nearest_station_name": "Nearest public station postcode coordinate by straight-line distance.",
            "nearest_station_distance_km": "Straight-line distance in kilometres; not routing or coverage.",
        },
        "Borough Station Proximity Dictionary",
    )
    write_memos(published, comparison, borough_proximity)
    write_provenance(raw_sha, published)
    plot_figures(comparison, borough_proximity)

    for path in [
        PUBLISHED_PARQUET,
        PUBLISHED_PROVENANCE,
        PUBLISHED_DICTIONARY,
        PUBLISHED_DQ_MEMO,
        COMPARISON_PARQUET,
        COMPARISON_DICTIONARY,
        COMPARISON_DQ_MEMO,
        BOROUGH_PROXIMITY_PARQUET,
        BOROUGH_PROXIMITY_DICTIONARY,
        BOROUGH_PROXIMITY_DQ_MEMO,
        FIG_DIR / "fig_station_d1_anchor_shift_top15.png",
        FIG_DIR / "fig_borough_nearest_station_proximity.png",
    ]:
        print(f"  wrote {path.relative_to(PROJECT_ROOT)}", flush=True)
    print("Done.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
