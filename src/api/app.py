"""
Flask backend for the LFB visual-analytics dashboard.

This module implements the JSON API the D3 front end (§5.4, future) reads
to render the linked-view borough panels. The app deliberately exposes
*aggregations only*, never the raw 293,646-row canonical incident table:
the front end has no need for per-incident detail in the borough view, and
keeping the API at aggregate granularity simplifies both the size of the
JSON payload and the privacy posture (no precise coordinates leave the
backend through this endpoint).

Run from the project root:

    flask --app src.api.app:create_app run

or programmatically (e.g.\\ in tests):

    from src.api.app import create_app
    app = create_app()

The borough summary parquet is loaded once at app-creation time; subsequent
requests filter the in-memory DataFrame and serialise the matched rows.
For the 2,574-row borough summary this stays interactive without any
external store; filtered requests are around 1 ms on the development
MacBook, while the unfiltered full response is around 1 MB / 18 ms.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import pandas as pd
from flask import Flask, jsonify, request, send_from_directory

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BOROUGH_SUMMARY_PATH = (
    PROJECT_ROOT / "data" / "processed" / "lfb_borough_summary_2024_2026.parquet"
)
BOROUGH_BOUNDARIES_PATH = (
    PROJECT_ROOT / "data" / "processed" / "london_borough_boundaries.geojson"
)
STATION_LOCATIONS_PATH = (
    PROJECT_ROOT / "data" / "processed" / "lfb_station_locations_2024_2026.parquet"
)
BOROUGH_CENTROIDS_PATH = (
    PROJECT_ROOT / "data" / "processed" / "lfb_borough_centroids_2024_2026.parquet"
)
DASHBOARD_DIR = PROJECT_ROOT / "src" / "dashboard"

# Columns clients are allowed to filter on. Unknown filter keys are
# rejected with HTTP 400 so that callers cannot (e.g.) accidentally
# query for a column that does not exist and silently get the full
# dataset back.
FILTERABLE_COLUMNS = ("borough_canonical", "year_month", "IncidentGroup")

# Disclaimer attached verbatim to every footprint-scenario response, so
# that any downstream visualisation or screenshot cannot drop the framing.
# The "footprint" wording (rather than "coverage" or "nearest station") is
# load-bearing: per the §5.6 deviation, both the borough and station
# anchors used here are *incident-derived centroids* of where calls have
# happened in the 2024-2026 slice, NOT the borough's polygonal centre or
# the brick-and-mortar fire-station building location.
FOOTPRINT_PROXY_DISCLAIMER = (
    "Exploratory proxy only. Distances are straight-line OSGB36 metres "
    "between the borough's incident centroid and the station's responsibility-"
    "footprint centroid; both anchors are derived from the canonical incident "
    "table, not from LFB's published station-locations release. Bispo et al. "
    "2023 (r=0.96 Euclidean vs road-network distance) licenses the use of "
    "straight-line distance in this footprint proxy. This is not a routing-"
    "grade dispatch model, not a coverage measure in the OR location-allocation "
    "sense, and not a station-relocation recommendation. See §5.6 of the "
    "report for the full deviation note against §4.2 N1."
)


def _row_to_jsonable(row: dict[str, Any]) -> dict[str, Any]:
    """
    Convert a pandas row dict into a JSON-safe dict.

    Two issues need handling:
    * NaN floats are not JSON-serialisable per RFC 8259, so they become None.
    * pandas nullable booleans (pd.NA) need the same treatment.
    """
    out: dict[str, Any] = {}
    for k, v in row.items():
        if v is pd.NA:
            out[k] = None
        elif isinstance(v, float) and math.isnan(v):
            out[k] = None
        elif isinstance(v, (pd.Timestamp,)):
            out[k] = v.isoformat()
        else:
            out[k] = v
    return out


def create_app(
    parquet_path: Path | None = None,
    boundaries_path: Path | None = None,
    dashboard_dir: Path | None = None,
    station_locations_path: Path | None = None,
    borough_centroids_path: Path | None = None,
) -> Flask:
    """
    Build and configure the Flask app.

    The function takes explicit artefact paths so tests can point the app
    at fixtures, but production code can call it with no arguments and get
    the canonical project paths.
    """
    app = Flask(__name__)

    path = parquet_path or BOROUGH_SUMMARY_PATH
    if not path.exists():
        raise FileNotFoundError(
            f"borough-summary parquet not found at {path}; "
            "run `python src/data/build_borough_summary.py` first"
        )

    boundary_path = boundaries_path or BOROUGH_BOUNDARIES_PATH
    if not boundary_path.exists():
        raise FileNotFoundError(
            f"borough-boundary GeoJSON not found at {boundary_path}; "
            "download the GLA London Borough layer first"
        )

    static_dir = dashboard_dir or DASHBOARD_DIR

    stations_path = station_locations_path or STATION_LOCATIONS_PATH
    if not stations_path.exists():
        raise FileNotFoundError(
            f"station-locations parquet not found at {stations_path}; "
            "run `python src/data/build_station_locations.py` first"
        )
    centroids_path = borough_centroids_path or BOROUGH_CENTROIDS_PATH
    if not centroids_path.exists():
        raise FileNotFoundError(
            f"borough-centroids parquet not found at {centroids_path}; "
            "run `python src/data/build_borough_centroids.py` first"
        )

    summary = pd.read_parquet(path)
    stations = pd.read_parquet(stations_path)
    centroids = pd.read_parquet(centroids_path)

    app.config["BOROUGH_SUMMARY"] = summary
    app.config["BOROUGH_SUMMARY_PATH"] = str(path)
    app.config["BOROUGH_BOUNDARIES_PATH"] = str(boundary_path)
    app.config["DASHBOARD_DIR"] = str(static_dir)
    app.config["STATION_LOCATIONS_PATH"] = str(stations_path)
    app.config["BOROUGH_CENTROIDS_PATH"] = str(centroids_path)

    @app.get("/health")
    def health() -> Any:
        return jsonify(
            {
                "status": "ok",
                "backing_artefact": Path(app.config["BOROUGH_SUMMARY_PATH"]).name,
                "boundary_artefact": Path(
                    app.config["BOROUGH_BOUNDARIES_PATH"]
                ).name,
                "rows": int(len(summary)),
                "columns": list(summary.columns),
            }
        )

    @app.get("/")
    @app.get("/dashboard")
    def dashboard() -> Any:
        return send_from_directory(static_dir, "index.html")

    @app.get("/dashboard/<path:filename>")
    def dashboard_asset(filename: str) -> Any:
        return send_from_directory(static_dir, filename)

    @app.get("/api/borough_boundaries")
    def borough_boundaries() -> Any:
        return send_from_directory(
            boundary_path.parent,
            boundary_path.name,
            mimetype="application/geo+json",
        )

    @app.get("/api/borough_summary")
    def borough_summary() -> Any:
        # Reject unknown filter keys explicitly. This is the
        # "no silent full-table dump" guard.
        unknown = set(request.args.keys()) - set(FILTERABLE_COLUMNS)
        if unknown:
            return (
                jsonify(
                    {
                        "error": "unknown filter keys",
                        "unknown_keys": sorted(unknown),
                        "allowed_keys": list(FILTERABLE_COLUMNS),
                    }
                ),
                400,
            )

        df = summary
        filters_applied: dict[str, list[str]] = {}
        for col in FILTERABLE_COLUMNS:
            values = request.args.getlist(col)
            if values:
                df = df[df[col].isin(values)]
                filters_applied[col] = values

        rows = [_row_to_jsonable(r) for r in df.to_dict(orient="records")]
        return jsonify(
            {
                "rows": rows,
                "row_count": len(rows),
                "filters_applied": filters_applied,
            }
        )

    @app.get("/api/station_footprints")
    def station_footprints() -> Any:
        """
        Return the per-station incident-derived footprint centroids. The
        endpoint is named ``footprints`` (not ``locations``) because the
        underlying parquet is derived from the canonical incident table,
        not from LFB's published station-locations release; see §5.6.
        """
        rows = [_row_to_jsonable(r) for r in stations.to_dict(orient="records")]
        return jsonify(
            {
                "rows": rows,
                "row_count": len(rows),
                "disclaimer": FOOTPRINT_PROXY_DISCLAIMER,
            }
        )

    @app.get("/api/footprint_scenario")
    def footprint_scenario() -> Any:
        """
        F4 closure-scenario calculation, framed as a footprint proxy: given
        a list of stations to remove, return the new nearest-station-
        \\emph{footprint} distance from each borough's incident centroid.
        ``footprint`` rather than ``coverage`` because both the borough
        anchor and the station anchor are incident-derived centroids; see
        §5.6 for the full deviation note against §4.2 N1.

        The list is supplied via repeated `remove` query keys (so
        `?remove=Soho&remove=Paddington` removes both). An empty `remove`
        list returns the baseline (no-removal) result.

        The disclaimer field is attached verbatim so that any downstream
        consumer cannot drop the framing.
        """
        # Reject any unknown query key (same "no silent full-table dump"
        # philosophy as /api/borough_summary).
        allowed = {"remove"}
        unknown = set(request.args.keys()) - allowed
        if unknown:
            return (
                jsonify(
                    {
                        "error": "unknown query keys",
                        "unknown_keys": sorted(unknown),
                        "allowed_keys": sorted(allowed),
                    }
                ),
                400,
            )

        remove = request.args.getlist("remove")
        # Reject removals naming stations that do not exist; otherwise a
        # typo silently returns the baseline result.
        known_stations = set(stations["station_name"])
        unknown_stations = [s for s in remove if s not in known_stations]
        if unknown_stations:
            return (
                jsonify(
                    {
                        "error": "unknown station names in remove list",
                        "unknown_stations": sorted(set(unknown_stations)),
                    }
                ),
                400,
            )

        open_stations = stations[~stations["station_name"].isin(remove)]
        if open_stations.empty:
            return (
                jsonify(
                    {
                        "error": "every station footprint removed; no footprint scenario to compute",
                        "stations_removed": sorted(set(remove)),
                    }
                ),
                400,
            )

        # Vectorised nearest-neighbour over the 33 borough centroids x
        # (102 - len(remove)) open stations. Trivially small; no spatial
        # index needed.
        s_east = open_stations["easting_centroid_m"].to_numpy()
        s_north = open_stations["northing_centroid_m"].to_numpy()
        s_names = open_stations["station_name"].to_numpy()

        result_rows: list[dict[str, Any]] = []
        for _, b in centroids.iterrows():
            de = s_east - float(b["easting_centroid_m"])
            dn = s_north - float(b["northing_centroid_m"])
            d2 = de * de + dn * dn
            best = int(d2.argmin())
            result_rows.append(
                {
                    "borough_canonical": b["borough_canonical"],
                    "borough_centroid_lon": float(b["longitude"]),
                    "borough_centroid_lat": float(b["latitude"]),
                    "nearest_footprint_station_name": str(s_names[best]),
                    "nearest_footprint_distance_m": round(float(d2[best] ** 0.5), 1),
                    "nearest_footprint_distance_km": round(
                        float(d2[best] ** 0.5) / 1000.0, 3
                    ),
                }
            )

        return jsonify(
            {
                "rows": result_rows,
                "row_count": len(result_rows),
                "stations_removed": sorted(set(remove)),
                "stations_open_count": int(len(open_stations)),
                "disclaimer": FOOTPRINT_PROXY_DISCLAIMER,
            }
        )

    return app


# Convenience factory for `flask run`.
app = None  # populated lazily below if invoked via `flask run`


def _get_app() -> Flask:
    global app
    if app is None:
        app = create_app()
    return app


if __name__ == "__main__":
    _get_app().run(debug=False)
