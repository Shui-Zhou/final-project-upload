"""Smoke tests for report-side results/evaluation figures."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIG_DIR = (
    PROJECT_ROOT
    / "report"
    / "Final Report Latex Template (Data Science)"
    / "figures"
    / "results_evaluation"
)
EARLY_CONTEXT_DIR = (
    PROJECT_ROOT
    / "report"
    / "Final Report Latex Template (Data Science)"
    / "figures"
    / "early_context"
)
SUMMARY_JSON = PROJECT_ROOT / "data" / "processed" / "lfb_report_evaluation_figures_summary.json"

EXPECTED_FIGURES = [
    EARLY_CONTEXT_DIR / "fig_motivation_borough_exceedance_map.png",
    EARLY_CONTEXT_DIR / "fig_coordinate_uncertainty_implications.png",
    EARLY_CONTEXT_DIR / "fig_linked_view_wireframe.png",
    FIG_DIR / "fig_borough_exceedance_ranking.png",
    FIG_DIR / "fig_incident_group_response_distribution.png",
    FIG_DIR / "fig_precise_coordinate_coverage_by_borough.png",
    FIG_DIR / "fig_temporal_incident_density_heatmap.png",
    FIG_DIR / "fig_false_alarm_sensitivity_ranking.png",
    FIG_DIR / "fig_precise_spatial_density_hexbin.png",
]

FIGURE_MEMO_STEMS = {
    "fig_motivation_borough_exceedance_map.png": "motivation_borough_exceedance_map",
    "fig_coordinate_uncertainty_implications.png": "coordinate_uncertainty_implications",
    "fig_linked_view_wireframe.png": "linked_view_wireframe",
    "fig_borough_exceedance_ranking.png": "borough_exceedance_ranking",
    "fig_incident_group_response_distribution.png": "incident_group_response_distribution",
    "fig_precise_coordinate_coverage_by_borough.png": "precise_coordinate_coverage",
    "fig_temporal_incident_density_heatmap.png": "temporal_incident_density",
    "fig_false_alarm_sensitivity_ranking.png": "false_alarm_sensitivity",
    "fig_precise_spatial_density_hexbin.png": "precise_spatial_density",
}


@pytest.fixture(scope="module")
def summary() -> dict[str, object]:
    if not SUMMARY_JSON.exists():
        pytest.skip(
            f"report evaluation summary missing at {SUMMARY_JSON}; "
            "run `python src/data/build_report_evaluation_figures.py` first"
        )
    return json.loads(SUMMARY_JSON.read_text())


def test_report_evaluation_figures_exist_and_are_nonempty() -> None:
    missing = [str(path) for path in EXPECTED_FIGURES if not path.exists()]
    assert not missing
    for path in EXPECTED_FIGURES:
        assert path.stat().st_size > 10_000


def test_report_evaluation_memos_exist() -> None:
    for path in EXPECTED_FIGURES:
        stem = FIGURE_MEMO_STEMS[path.name]
        memo = PROJECT_ROOT / "data" / "processed" / f"report_figure_{stem}_memo.md"
        assert memo.exists()
        text = memo.read_text()
        assert "Suggested Caption" in text
        assert "Denominator" in text


def test_report_evaluation_summary_core_invariants(summary: dict[str, object]) -> None:
    assert summary["row_count_main_incident_groups"] == 293_592

    ranking = summary["borough_ranking"]
    assert ranking["top_borough"] == "Hillingdon"
    assert 0.50 <= ranking["top_borough_exceedance_share"] <= 0.54

    motivation = summary["motivation_map"]
    assert motivation["boundary_join_missing"] == []
    assert motivation["top_three_boroughs"][0]["borough"] == "Hillingdon"

    coordinate_implications = summary["coordinate_uncertainty_implications"]
    assert 0.37 <= coordinate_implications["precise_coordinate_share"] <= 0.39
    assert coordinate_implications["rounded_coordinate_valid_share"] > 0.99

    wireframe = summary["linked_view_wireframe"]
    assert "borough_map" in wireframe["components"]
    assert "ranking_table" in wireframe["components"]

    coverage = summary["coordinate_coverage"]
    assert 0.37 <= coverage["overall_precise_coordinate_share"] <= 0.39

    sensitivity = summary["false_alarm_sensitivity"]
    assert sensitivity["spearman_all_vs_excluding_false_alarms"] > 0.95
    assert sensitivity["spearman_all_vs_fire_only"] > 0.9

    temporal = summary["temporal_density"]["temporal_peak_cells"]
    assert set(temporal) == {"False Alarm", "Fire", "Special Service"}
