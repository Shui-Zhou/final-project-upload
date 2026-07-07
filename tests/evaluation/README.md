# Phase 3 Evaluation Assets

> Status: completed small-scale formative evaluation and supporting protocol files.
> Updated: 2026-07-07.
> Purpose: non-identifying index of the evaluation protocol and summary evidence used in Section 6.

## Files

| File | Strand | Output type |
|---|---|---|
| `strand1_heuristic_walkthrough_checklist.md` | Internal heuristic walk-through | Checklist used for dashboard readiness checks |
| `strand1_findings_summary.md` | Internal heuristic walk-through | Non-identifying defect and closure summary |
| `strand2_thinkaloud_task_script.md` | Compact think-aloud | Task-based inspection script used with Participants 1--3 |
| `strand3_rq5_uncertainty_probe.md` | Uncertainty / caveat probe | Prompt set for denominator, coordinate-coverage, and station-coverage interpretation |
| `observation_log_template.md` | All participant sessions | Local per-session observation template; completed session notes are not committed |
| `strand2_strand3_findings_summary.md` | Participant summary | Aggregate, non-identifying findings for Participants 1--3 |
| `capture_dashboard_figures.py` | Figure capture support | Utility for dashboard screenshot capture |

## Evidence Boundaries

The participant evaluation is a compact formative interpretability check, not a statistically generalisable usability study. Three voluntary participants completed task-based dashboard inspection while thinking aloud. The recorded summary focuses on comparison behaviour, uncertainty noticing, denominator checking, and the risk of overclaiming station coverage.

No sensitive personal data is stored in this repository. Per-session facilitator notes are anonymised at source and are used only to derive aggregate findings; only non-identifying summaries and reusable evaluation instruments belong in committed files.

## Validation Tie-In

Before sessions or figure capture, run the project health checks from `RUNBOOK.md`:

```bash
python -m pytest tests/ -q
python -m compileall src
```

Then open the dashboard and confirm the map, monthly trend, response distribution, and ranking table render without console errors.
