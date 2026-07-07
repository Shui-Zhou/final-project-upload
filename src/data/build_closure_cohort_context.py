"""Build Taylor (2015) closure-cohort context for the final report.

This script computes a descriptive 2024-2026 borough-level cross-check against
the 2014 station-closure cohort reported by Taylor (2015). It is not a causal
model, a coverage model, a relocation claim, or a replication of Taylor's
500 m dwelling-fire analysis.
"""

from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data" / "processed"
REPORT_DIR = PROJECT_ROOT / "report" / "Final Report Latex Template (Data Science)"
FIG_DIR = REPORT_DIR / "figures" / "results_evaluation"

CANONICAL_PATH = DATA_DIR / "lfb_canonical_2024_2026.parquet"
OUT_PARQUET = DATA_DIR / "lfb_closure_cohort_context_2024_2026.parquet"
PROVENANCE_PATH = DATA_DIR / "lfb_closure_cohort_context_2024_2026_provenance.json"
DQ_MEMO_PATH = DATA_DIR / "lfb_closure_cohort_context_2024_2026_dq_memo.md"
FIGURE_PATH = FIG_DIR / "fig_taylor_closure_cohort_context.png"

INCIDENT_GROUPS = ["False Alarm", "Fire", "Special Service"]

# REVIEW-GATE: verify against Taylor (2015)/LFB LSP5 before prose is final.
CLOSURE_STATION_BOROUGH_MAPPING = [
    {"station": "Belsize", "borough_canonical": "Camden", "taylor_status": "affected"},
    {"station": "Downham", "borough_canonical": "Lewisham", "taylor_status": "affected"},
    {"station": "Kingsland", "borough_canonical": "Hackney", "taylor_status": "affected"},
    {"station": "Knightsbridge", "borough_canonical": "Westminster", "taylor_status": "affected"},
    {"station": "Silvertown", "borough_canonical": "Newham", "taylor_status": "affected"},
    {"station": "Southwark", "borough_canonical": "Southwark", "taylor_status": "affected"},
    {"station": "Westminster", "borough_canonical": "Westminster", "taylor_status": "affected"},
    {"station": "Woolwich", "borough_canonical": "Greenwich", "taylor_status": "affected"},
    {"station": "Bow", "borough_canonical": "Tower Hamlets", "taylor_status": "unaffected"},
    {"station": "Clerkenwell", "borough_canonical": "Islington", "taylor_status": "unaffected"},
]


def display_borough_name(name: str) -> str:
    return name.replace(" And ", " and ").replace(" Upon ", " upon ")


def pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def load_canonical() -> pd.DataFrame:
    df = pd.read_parquet(CANONICAL_PATH)
    df = df[df["IncidentGroup"].isin(INCIDENT_GROUPS)].copy()
    df["exceeds_six_min_target"] = df["exceeds_six_min_target"].astype("boolean")
    return df


def build_context_table(df: pd.DataFrame) -> pd.DataFrame:
    recorded = df[df["response_time_seconds"].notna()].copy()
    stats = (
        recorded.groupby("borough_canonical")
        .agg(
            recorded_time_incidents=("IncidentNumber", "size"),
            recorded_time_exceedance_share=("exceeds_six_min_target", "mean"),
            median_response_min=("response_time_minutes", "median"),
            p90_response_min=("response_time_minutes", lambda s: s.quantile(0.9)),
        )
        .reset_index()
    )
    total_counts = (
        df.groupby("borough_canonical")
        .agg(total_incidents=("IncidentNumber", "size"))
        .reset_index()
    )
    stats = stats.merge(total_counts, on="borough_canonical", how="left")
    stats["recorded_time_share"] = (
        stats["recorded_time_incidents"] / stats["total_incidents"]
    )

    closure = pd.DataFrame(CLOSURE_STATION_BOROUGH_MAPPING)
    stations_by_borough = (
        closure.groupby("borough_canonical")
        .agg(
            closure_stations=("station", lambda s: ", ".join(sorted(s))),
            taylor_affected_station_count=(
                "taylor_status",
                lambda s: int((s == "affected").sum()),
            ),
            taylor_unaffected_station_count=(
                "taylor_status",
                lambda s: int((s == "unaffected").sum()),
            ),
        )
        .reset_index()
    )
    stats = stats.merge(stations_by_borough, on="borough_canonical", how="left")
    stats["closure_stations"] = stats["closure_stations"].fillna("")
    stats["taylor_affected_station_count"] = (
        stats["taylor_affected_station_count"].fillna(0).astype(int)
    )
    stats["taylor_unaffected_station_count"] = (
        stats["taylor_unaffected_station_count"].fillna(0).astype(int)
    )

    def cohort(row: pd.Series) -> str:
        if row["taylor_affected_station_count"] > 0:
            return "Taylor affected-closure borough"
        if row["taylor_unaffected_station_count"] > 0:
            return "Taylor unaffected-closure borough"
        return "Other borough"

    stats["closure_cohort"] = stats.apply(cohort, axis=1)
    return stats.sort_values("recorded_time_exceedance_share", ascending=False).reset_index(
        drop=True
    )


def summary_by_cohort(table: pd.DataFrame) -> dict[str, Any]:
    grouped = (
        table.groupby("closure_cohort")
        .agg(
            borough_count=("borough_canonical", "size"),
            mean_recorded_time_exceedance_share=(
                "recorded_time_exceedance_share",
                "mean",
            ),
            median_recorded_time_exceedance_share=(
                "recorded_time_exceedance_share",
                "median",
            ),
            recorded_time_incidents=("recorded_time_incidents", "sum"),
        )
        .sort_index()
    )
    return {
        cohort: {
            key: int(value) if key in {"borough_count", "recorded_time_incidents"} else float(value)
            for key, value in row.items()
        }
        for cohort, row in grouped.iterrows()
    }


def plot_context(table: pd.DataFrame, summary: dict[str, Any]) -> None:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    plt.style.use("seaborn-v0_8-whitegrid")

    closure_rows = table[table["closure_cohort"] != "Other borough"].copy()
    closure_rows = closure_rows.sort_values("recorded_time_exceedance_share")
    colors = closure_rows["closure_cohort"].map(
        {
            "Taylor affected-closure borough": "#b91c1c",
            "Taylor unaffected-closure borough": "#2563eb",
        }
    )

    fig, (ax_bar, ax_strip) = plt.subplots(
        1, 2, figsize=(12.8, 6.4), gridspec_kw={"width_ratios": [1.25, 1]}
    )

    ax_bar.barh(
        [display_borough_name(x) for x in closure_rows["borough_canonical"]],
        closure_rows["recorded_time_exceedance_share"] * 100,
        color=colors,
    )
    other_mean = summary["Other borough"]["mean_recorded_time_exceedance_share"] * 100
    ax_bar.axvline(other_mean, color="#111827", lw=1.2, ls="--")
    ax_bar.set_xlabel("Recorded-time exceedance share (%)")
    ax_bar.set_title("2024-2026 boroughs containing 2014 closure stations")
    ax_bar.text(
        other_mean + 0.5,
        -0.55,
        "Other-borough mean",
        fontsize=8.5,
        color="#111827",
    )

    order = [
        "Taylor affected-closure borough",
        "Taylor unaffected-closure borough",
        "Other borough",
    ]
    x_positions = np.arange(len(order))
    for xpos, cohort in zip(x_positions, order, strict=True):
        values = table.loc[
            table["closure_cohort"] == cohort, "recorded_time_exceedance_share"
        ].to_numpy()
        jitter = np.linspace(-0.08, 0.08, len(values)) if len(values) > 1 else np.array([0])
        ax_strip.scatter(
            np.full(len(values), xpos) + jitter,
            values * 100,
            s=70,
            color={
                "Taylor affected-closure borough": "#b91c1c",
                "Taylor unaffected-closure borough": "#2563eb",
                "Other borough": "#6b7280",
            }[cohort],
            alpha=0.82,
        )
        ax_strip.hlines(
            values.mean() * 100,
            xpos - 0.25,
            xpos + 0.25,
            color="#111827",
            lw=1.5,
        )
    ax_strip.set_xticks(
        x_positions,
        ["Affected\nclosure\nboroughs", "Unaffected\nclosure\nboroughs", "Other\nboroughs"],
    )
    ax_strip.set_ylabel("Recorded-time exceedance share (%)")
    ax_strip.set_title("Descriptive cohort comparison")

    fig.suptitle(
        "Taylor (2015) closure cohort as descriptive context, not causal evidence",
        fontsize=13,
        y=0.99,
    )
    fig.text(
        0.02,
        0.015,
        "Caveat: Taylor analyses dwelling fires on 500 m squares; this figure uses 2024-2026 all-main-incident borough aggregates.",
        fontsize=8.8,
        color="#475569",
    )
    fig.tight_layout(rect=[0, 0.04, 1, 0.95])
    fig.savefig(FIGURE_PATH, dpi=220)
    plt.close(fig)


def write_sidecars(table: pd.DataFrame, summary: dict[str, Any]) -> None:
    provenance = {
        "artefact": "lfb_closure_cohort_context_2024_2026",
        "schema_version": "1.0",
        "source": {
            "canonical_relative_path": str(CANONICAL_PATH.relative_to(PROJECT_ROOT)),
            "literature_anchor": "Taylor (2015) spatial survival analysis, project.bib key spatial2015",
        },
        "mapping_review_gate": (
            "REVIEW-GATE: verify station-to-borough mapping against Taylor (2015)/LFB LSP5 before prose is final."
        ),
        "closure_station_borough_mapping": CLOSURE_STATION_BOROUGH_MAPPING,
        "filters": {
            "incident_groups": INCIDENT_GROUPS,
            "response_time": "non-null FirstPumpArriving_AttendanceTime only",
        },
        "build": {
            "extracted_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
            "script": str(Path(__file__).relative_to(PROJECT_ROOT)),
            "python_version": sys.version.split()[0],
            "pandas_version": pd.__version__,
        },
        "row_counts": {
            "borough_rows": int(len(table)),
            "closure_station_rows": int(len(CLOSURE_STATION_BOROUGH_MAPPING)),
            "affected_station_rows": int(
                sum(
                    item["taylor_status"] == "affected"
                    for item in CLOSURE_STATION_BOROUGH_MAPPING
                )
            ),
            "unaffected_station_rows": int(
                sum(
                    item["taylor_status"] == "unaffected"
                    for item in CLOSURE_STATION_BOROUGH_MAPPING
                )
            ),
        },
        "summary_by_cohort": summary,
        "honesty_note": (
            "Descriptive borough-level context only. Do not read as causal closure evidence, "
            "coverage evidence, relocation evidence, or a replication of Taylor's 500 m dwelling-fire model."
        ),
    }
    PROVENANCE_PATH.write_text(json.dumps(provenance, indent=2, ensure_ascii=False) + "\n")

    affected = table[table["closure_cohort"] == "Taylor affected-closure borough"]
    unaffected = table[table["closure_cohort"] == "Taylor unaffected-closure borough"]
    other = table[table["closure_cohort"] == "Other borough"]
    lines = [
        "# Taylor Closure Cohort Context DQ Memo",
        "",
        "> Auto-generated by `src/data/build_closure_cohort_context.py`.",
        "",
        "## Scope",
        "",
        "This memo compares 2024-2026 borough-level recorded-time exceedance shares for boroughs containing stations in Taylor's 2014 closure cohort against other boroughs.",
        "",
        "It is descriptive only. Taylor (2015) analyses dwelling fires around 500 m grid squares; this project uses borough-level all-main-incident aggregates. The figure must not be described as causal closure evidence, coverage evidence, or a relocation claim.",
        "",
        "## Review Gate",
        "",
        "- REVIEW-GATE: verify the station-to-borough mapping against Taylor (2015)/LFB LSP5 before prose is final.",
        "",
        "## Cohort Summary",
        "",
        "| Cohort | Boroughs | Mean exceedance | Median exceedance | Recorded-time incidents |",
        "|---|---:|---:|---:|---:|",
    ]
    for cohort, values in summary.items():
        lines.append(
            f"| {cohort} | {values['borough_count']} | "
            f"{pct(values['mean_recorded_time_exceedance_share'])} | "
            f"{pct(values['median_recorded_time_exceedance_share'])} | "
            f"{values['recorded_time_incidents']:,} |"
        )
    lines.extend(
        [
            "",
            "## Closure Boroughs",
            "",
            "| Borough | Taylor station(s) | Taylor status | Recorded-time exceedance | Recorded-time incidents |",
            "|---|---|---|---:|---:|",
        ]
    )
    for row in pd.concat([affected, unaffected]).sort_values("borough_canonical").itertuples():
        lines.append(
            f"| {display_borough_name(row.borough_canonical)} | {row.closure_stations} | "
            f"{row.closure_cohort} | {pct(row.recorded_time_exceedance_share)} | "
            f"{row.recorded_time_incidents:,} |"
        )
    lines.extend(
        [
            "",
            "## Other-Borough Range",
            "",
            f"- Other borough count: {len(other):,}",
            f"- Other-borough exceedance range: {pct(other['recorded_time_exceedance_share'].min())} to {pct(other['recorded_time_exceedance_share'].max())}.",
        ]
    )
    DQ_MEMO_PATH.write_text("\n".join(lines) + "\n")


def validation_checks(table: pd.DataFrame) -> None:
    if len(table) != 33:
        raise RuntimeError(f"expected 33 borough rows, got {len(table)}")
    if table["recorded_time_exceedance_share"].isna().any():
        raise RuntimeError("borough exceedance shares contain NaN")
    affected_boroughs = set(
        table.loc[
            table["closure_cohort"] == "Taylor affected-closure borough",
            "borough_canonical",
        ]
    )
    unaffected_boroughs = set(
        table.loc[
            table["closure_cohort"] == "Taylor unaffected-closure borough",
            "borough_canonical",
        ]
    )
    if len(affected_boroughs) != 7:
        raise RuntimeError(f"expected 7 affected-closure boroughs, got {affected_boroughs}")
    if unaffected_boroughs != {"Tower Hamlets", "Islington"}:
        raise RuntimeError(f"unexpected unaffected-closure boroughs: {unaffected_boroughs}")
    if not FIGURE_PATH.exists() or FIGURE_PATH.stat().st_size < 10_000:
        raise RuntimeError(f"figure missing or unexpectedly small: {FIGURE_PATH}")


def main() -> int:
    df = load_canonical()
    table = build_context_table(df)
    summary = summary_by_cohort(table)
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    OUT_PARQUET.parent.mkdir(parents=True, exist_ok=True)
    table.to_parquet(OUT_PARQUET, index=False)
    plot_context(table, summary)
    write_sidecars(table, summary)
    validation_checks(table)
    print(f"Wrote {OUT_PARQUET.relative_to(PROJECT_ROOT)}")
    print(f"Wrote {FIGURE_PATH.relative_to(PROJECT_ROOT)}")
    print(f"Wrote {PROVENANCE_PATH.relative_to(PROJECT_ROOT)}")
    print(f"Wrote {DQ_MEMO_PATH.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
