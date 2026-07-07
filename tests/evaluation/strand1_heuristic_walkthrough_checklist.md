# Strand 1 — Heuristic Walk-Through Checklist

> Status: protocol scaffold; no walk-through has been run yet.  
> Updated: 2026-05-02 (Phase 3 evaluation assets first iteration).
> Owner: author / internal reviewer (n = 1).  
> Time budget: ~30 min on a 16 GB MacBook.

## Purpose

Closes Strand 1 of §4.6 (Evaluation Plan): a single-reviewer heuristic walk-through against four visualisation-adapted heuristic clusters. Each finding gets logged with severity and pinned to a §6 row so the §6 prose can quote it without invention.

This is **not** an empirical result. It is a defect log. Outputs feed (a) `§5.6` deviation entries if a blocker is found and (b) `§6` write-up if heuristics anchor specific evaluation claims.

## Setup

1. Pull the latest commit; verify `git status --short` is clean.
2. Build all data artefacts (`RUNBOOK.md` → "Rebuild Data Artefacts").
3. Run `python -m pytest tests/ -q`; expect 70 passed.
4. Start dashboard: `flask --app src.api.app:create_app run --debug --port 5057`.
5. Open `http://127.0.0.1:5057/dashboard` in a clean browser window (no extensions interfering with rendering).
6. Set viewport to 1440 × 900 desktop and (separately) 390 × 844 mobile.

Record the commit SHA, browser, and viewport at the top of the observation log entry.

## Severity Scale

- **Blocker** — falsifies a §6 claim or breaks a §5 invariant; must be fixed before any think-aloud session.
- **Major** — likely to mislead a participant or cause a participant to fail an RQ task; fix before Strand 2.
- **Minor** — interpretable hint or polish issue; capture for later iteration.
- **Cosmetic** — pure presentation; safe to defer to the second-iteration UI pass.

## Heuristic Clusters

Heuristics group around the four §4.6 clusters: *exploration*, *communication*, *abstraction*, and *cognitive fit*. Each row pins to the §6 row that the heuristic informs so that any defect carries forward into the right evaluation paragraph.

### E — Exploration

| ID | Heuristic | Pass criterion | §6 anchor | Severity if failed |
|---|---|---|---|---|
| E1 | Borough selection round-trips across all linked panels (map ↔ trend ↔ distribution ↔ ranking). | Clicking any borough on the map updates the trend, distribution, and ranking panels within ≤ 200 ms. | §6.3 row 1 (linked brushing) | Major |
| E2 | Month filter is reachable without losing the brushed borough selection. | After applying a month filter the previously-brushed borough remains selected. Year / weekday / hour controls are out of scope for the current dashboard iteration. | §6.3 row 2 (Filter category) | Major |
| E3 | Returning to a default state is a single, obvious action. | A `Reset` or `Clear filters` affordance returns the dashboard to the no-filter state in one click. | §6.3 row 4 (perceptual budget) | Minor |
| E4 | Panels degrade gracefully when a selection has zero rows. | An empty selection renders an explicit "no rows match" message rather than a blank panel. | §6.3 row 1 | Major |

### C — Communication

| ID | Heuristic | Pass criterion | §6 anchor | Severity if failed |
|---|---|---|---|---|
| C1 | Choropleth fill encodes the 6-min exceedance share with a teal → amber → red ramp matching the legend. | The legend gradient direction matches the rendered fill direction; high values render red, low values teal. | §6.2 row 1 | Blocker |
| C2 | Trend pane labels both traces (incident count vs. exceedance share) and uses a shared time axis. | Both traces are labelled, the y-axis units are unambiguous, and hovering a month surfaces both values. | §6.2 row 2 | Major |
| C3 | The 6-minute target is visually distinct from the data on the distribution pane. | A dashed reference line at 6 min is rendered with a contrasting colour and labelled. | §6.2 row 3 | Major |
| C4 | The denominator gap for exceedance-share tooltips is captured without forcing a UI rewrite before sessions. | If tooltips do not yet state "of *N* incidents with a recorded time", record this as a known first-iteration limitation for Strand 3 rather than a Strand-2 blocker. | §6.4 row 2 (missing-time hedge) | Minor |
| C5 | The footprint scenario is labelled as exploratory, not coverage. | Any UI string for the footprint endpoint includes "footprint" / "exploratory proxy" wording, never "coverage" without qualification. | §7.2 (public misinterpretation) | Blocker |

### A — Abstraction

| ID | Heuristic | Pass criterion | §6 anchor | Severity if failed |
|---|---|---|---|---|
| A1 | Borough-month aggregation is the default; per-incident records are not exposed in the UI. | No view exposes the canonical 293,646-row table; aggregations are the only artefact. | §7.1 (PII / privacy) | Blocker |
| A2 | Precise-coordinate-coverage column is shown in the ranking table. | The ranking table includes a per-borough precise-coord-coverage value. | §6.4 row 1 | Major |
| A3 | Mobilisation-derived deployment claims, where present, are restricted to the matched-only subset. | Any UI text that quotes appliance-level deployment numbers explicitly says "matched to canonical" or filters via `matches_canonical_incident == True`. | §6.4 row 4 | Blocker |
| A4 | The footprint scenario disclaimer is attached to every payload that cites it. | The disclaimer string is present in every `/api/footprint_scenario` response; if a future UI panel consumes the endpoint, the same wording must be visible there. | §7.2 | Blocker |

### F — Cognitive Fit

| ID | Heuristic | Pass criterion | §6 anchor | Severity if failed |
|---|---|---|---|---|
| F1 | Spatial pattern → choropleth: the map is the dominant pane, sized for the borough-pattern reading task. | The choropleth occupies ≥ 40% of the dashboard's screen real estate at desktop viewport. | §6.2 row 1 | Minor |
| F2 | Temporal pattern → trend pane: line chart, not bar chart, for the 26-month series. | The trend pane uses a connected line, not isolated bars. | §6.2 row 2 | Minor |
| F3 | Variation → distribution pane: median-to-p95 range with the target line, not a single mean number. | The distribution pane shows at least the median and p95; the second-iteration upgrade to the dotplot is *not* required to pass this heuristic. | §6.2 row 3 | Major |
| F4 | Ranking task → table, not chart. | A ranked table view is present and ordered by exceedance-share. Interactive column sorting is a second-iteration affordance, not a Strand-2 prerequisite. | §6.2 row 4 | Minor |
| F5 | Mobile viewport (390 px) does not produce horizontal overflow. | `body.scrollWidth` equals viewport width; trend-pane month-tick density adapts to the narrower viewport. | §6.3 row 4 | Minor |

## Walk-Through Procedure

1. For each heuristic above, exercise the dashboard until the pass criterion is either met or falsified.
2. Record verdict (`pass`, `fail`, `n/a`) and a one-line note in the observation log (`observation_log_template.md`).
3. If `fail`, set the severity per the scale above. Stop the walk-through and log the blocker before proceeding if the severity is `Blocker`.
4. After the four clusters, run the validation commands once more to confirm nothing was perturbed: `python -m pytest tests/ -q && python -m compileall src`.

## Outputs Expected

- A single completed observation-log entry referencing this checklist.
- Zero `Blocker` findings before Strand 2 think-aloud sessions begin. Any `Blocker` is fixed and the affected heuristic re-tested before participants are invited.
- All `Major` findings either fixed or carried as a §5.6 deviation entry with a recovery commit hash.

## Out of Scope

- Quantitative task-time measurement (that is the controlled-experiment scenario from `\cite{lam2011}` UP, explicitly out of scope per §4.6 / §6.5).
- Statistical generalisation. Strand 1 is `n = 1` by design.
- Any change to the §6 / §7 / §8 prose during the walk-through; defects are logged here, not back-written into the .tex files in this iteration.
