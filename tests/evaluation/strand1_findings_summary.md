# Strand 1 — Findings Summary

> Aggregate, non-identifying summary of the Strand 1 heuristic walk-through. Per `observation_log_template.md`, detailed per-session notes are anonymised at source and kept outside committed project artefacts; this file records the committed summary without local notes.
> Walk-through date: 2026-05-02.  
> Reviewer: author-led static/API pass with live-browser verification.
> Method: static source-level audit of `src/dashboard/{index.html,dashboard.js,styles.css}` + programmatic API contract verification via the Flask `test_client` against the contract in `docs/API_CONTRACT.md`; followed by live-browser verification on the local Flask dashboard via Playwright at desktop/default and 390 × 844 mobile viewport.
> Source snapshot: dashboard first-iteration evaluation baseline.

## Verdict Table

| ID | Cluster | Verdict | Severity | One-line note |
|---|---|---|---|---|
| E1 | Exploration | pass | n/a | `dashboard.js render()` re-renders all four panels on borough click; **live latency confirmed at 39.3 ms** (Chrome MCP, 2026-05-02 follow-up: Performance.now() before / after `dispatchEvent('click')` on a non-selected borough path; metric-exceed text changed from 66 % to 47 %). 39.3 ms ≪ 200 ms budget. |
| E2 | Exploration | pass | n/a | `state.borough` is independent of `state.month`; month-filter change does not mutate `state.borough`. Year / weekday / hour controls are out of scope for this dashboard iteration. |
| E3 | Exploration | fail | Minor | No explicit `Reset` / `Clear filters` affordance in the dashboard shell; user must re-pick original options manually. |
| E4 | Exploration | fixed | (was Major) | Original verdict: empty `(borough, month, group)` selection rendered dashes / blank panels with no explicit message. **Fix landed in this commit**: `src/dashboard/{index.html,dashboard.js,styles.css}` — adds a `#empty-state` element rendered when `rowForSelection()` returns undefined, with the text "No data for the selected borough · month · incident-group combination. Adjust the filters to a populated cell." Verified live (Chrome MCP, 2026-05-02 follow-up): banner appears with amber left border + cream background between metric strip and map when borough is forced to a non-existent value; banner hidden again when borough is restored. +18 lines across 3 files (≤ 30-line budget). |
| C1 | Communication | pass | n/a | Choropleth fill colour stops `#d9efed → #78c9c7 → #087f8c → #f0a13a → #c43d35` (teal → amber → red) match `styles.css` legend `linear-gradient(90deg, …)` exactly; high values render red. |
| C2 | Communication | pass | n/a | Trend pane labels both traces (`Incidents` teal solid, `Over 6 min` amber dashed) on a shared `year_month` axis; `axisBottom` tick density adapts to chart width. |
| C3 | Communication | pass | n/a | Distribution pane renders an amber dashed line at `x(6)` plus a `6 min` text label; visually distinct from the data marks. |
| C4 | Communication | fixed | (was Minor) | The tooltip now states that exceedance is "among recorded first-pump times" (`src/dashboard/dashboard.js`). Strand 3 P2 can still test whether users understand the denominator without treating the issue as an unfixed UI defect. |
| C5 | Communication | pass | n/a | The footprint endpoint is **not** consumed by the dashboard UI. The disclaimer string on `/api/footprint_scenario` and `/api/station_footprints` opens with "Exploratory proxy only…" and never uses the word "coverage" without qualification (verified via `test_client`). |
| A1 | Abstraction | pass | n/a | The HTTP surface exposes only the borough-summary aggregate (`/api/borough_summary`, 2,574 rows; ≈ 1.0 MiB unfiltered, ≈ 31 KiB borough-filtered), the boundary layer, station footprints, and the footprint scenario. The 293,646-row canonical incident table is not served. |
| A2 | Abstraction | pass | n/a | `index.html` line 84 declares the `Precise coords` column; `dashboard.js` line 373 binds `coord_precise_share` per row; the tooltip surfaces the same field for the hovered borough. |
| A3 | Abstraction | n/a | n/a | The dashboard does not surface mobilisation-derived deployment claims in this iteration. The `matches_canonical_incident` flag is enforced at the parquet layer (`src/data/build_mobilisations.py`) and verified by `tests/test_mobilisations.py`; UI exposure is deferred. |
| A4 | Abstraction | pass | n/a | `FOOTPRINT_PROXY_DISCLAIMER` is attached to every `/api/footprint_scenario` and `/api/station_footprints` response (`test_client` returns the expected `disclaimer` field on baseline, removal, and unknown-station-removed paths). |
| F1 | Cognitive Fit | pass | n/a | CSS grid `1.35fr / (1.35 + 0.75) ≈ 64 %` width × roughly 65 % height ≈ 42 % of the dashboard's screen real estate at desktop viewport, ≥ 40 % threshold. |
| F2 | Cognitive Fit | pass | n/a | Trend pane uses `d3.line()` for both the `Incidents` and `Over 6 min` traces; no bar marks. |
| F3 | Cognitive Fit | pass | n/a | Distribution pane shows median dot + median-to-p95 range + amber dashed 6-min reference line. The HOPs / quantile-dotplot upgrade remains a §4.4 / §6.2 row 3 second-iteration deliverable. |
| F4 | Cognitive Fit | pass | n/a | `selectedRows().sort(d3.descending(a.exceeds_six_min_share, b.exceeds_six_min_share))` orders the table by exceedance share. Interactive column sorting is intentionally deferred. |
| F5 | Cognitive Fit | pass | n/a | Playwright browser verification at 390 × 844 confirmed `document.body.scrollWidth === window.innerWidth` (390 = 390), `.dashboard-shell` scroll width = 390, and trend-pane tick density is reduced (16 visible tick labels at mobile width). No horizontal overflow observed. |

## Headline

**After the 2026-07-07 thesis-readiness pass: zero `Blocker`, zero open `Major`, one open `Minor`, and no manual-verification rows left unresolved.** Strand 2 / Strand 3 sessions were eligible at the current dashboard scope. E1 was confirmed live twice (39.3 ms in the closure commit; 13.9 ms in follow-up browser verification); E4 Major was fixed and visually verified; C4 tooltip denominator wording is now fixed; F5 mobile viewport was verified at 390 × 844 with no horizontal overflow.

Findings by severity (current):

- 0 × Blocker
- 0 × open Major (E4 fixed in this commit; previously the only Major)
- 1 × Minor: E3 (no Reset affordance)
- 0 × Cosmetic
- 1 × n/a: A3 (mobilisation UI deferred)
- 0 × unresolved manual-verification rows
- 14 × pass (E1, E2, C1, C2, C3, C5, A1, A2, A4, F1, F2, F3, F4, F5)
- 1 × fixed (E4)

## Decision

Per `strand1_heuristic_walkthrough_checklist.md` § Outputs Expected, Strand 2 requires both conditions: zero `Blocker` findings and all `Major` findings either fixed or carried as a §5.6 deviation entry with a recovery commit hash.

- **Zero Blocker** ✓
- **E4 Major fixed** in this commit via `src/dashboard/{index.html,dashboard.js,styles.css}` — option 1 in the prior decision table, executed before participant sessions. Recovery commit: this commit.
- **E1 latency confirmed live** ✓ (39.3 ms, ≪ 200 ms budget).
- **F5 mobile viewport confirmed** ✓ (Playwright 390 × 844 viewport; no horizontal overflow; reduced trend tick density observed).

The two `Minor` findings (E3, C4) are recorded for the §6 prose back-write iteration; they are not on the strict block-list for Strand 2 per the checklist's § Outputs Expected clause.

## Participant-Readiness Decision

Strand 2 / Strand 3 may be scheduled at the current dashboard scope. Keep the session count to the planned small-N range (3--5 classmates), keep detailed per-session notes outside committed project artefacts, and do not back-write §6 / §7 / §8 prose until after the sessions are complete.

E1 latency was confirmed live during the closure commit (Performance.now() probe → 39.3 ms) and again during follow-up browser verification (13.9 ms). E4 fix was visually verified by forcing an empty selection and observing the banner. F5 was verified with a 390 × 844 mobile viewport.

## What Was NOT Done in This Walk-Through

- Editing §5.6 deviation list. Not needed because E4 was fixed at the dashboard layer instead of carried as a deviation.
- Editing §6 / §7 / §8 prose during this earlier walk-through.
- Committing detailed per-session notes. Those notes are used for transparent coding, while this aggregate file is the committed artefact.
- Fixing the remaining Minor finding (E3 Reset). Carried for the second-iteration UI / N5 contract pass per `strand1_heuristic_walkthrough_checklist.md` § Outputs Expected.

## Tie-In with §6

Each verdict feeds at least one §6 row per `tests/evaluation/README.md` § Map to §6 Rows:

| Verdict | §6 anchor |
|---|---|
| E1, E4 | §6.3 row 1 |
| E2 | §6.3 row 2 |
| E3 | §6.3 row 4 |
| C1, F1 | §6.2 row 1 |
| C2, F2 | §6.2 row 2 |
| C3, F3 | §6.2 row 3 |
| C4 | §6.4 row 2 (and Strand-3 P2 follow-up) |
| C5, A4 | §6.4 row 3 + §7.2 |
| A1 | §7.1 |
| A2 | §6.4 row 1 |
| A3 | §6.4 row 4 (parquet-layer enforcement; UI deferred) |
| F4 | §6.2 row 4 |
| F5 | §6.3 row 4 |
