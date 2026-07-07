# Strand 3 — SQ4/SQ5 Uncertainty Probe (was: RQ5 Uncertainty Probe)

> Status: protocol used for the compact think-aloud evaluation with Participants 1--3.
> Updated: 2026-07-07. Filename retains `rq5` for link stability across earlier protocol references.
> Owner: facilitator (Joe).  
> Conducted: immediately after the four Strand-2 tasks, before the Lab Questionnaire and debrief.  
> Time budget: ≤ 5 min per participant.

## Purpose

Closes Strand 3 of §4.6 under the 2026-07-06 working RQ set (`PROJECT_BRIEF.md`):

- **SQ4** — how do data-quality constraints (privacy-suppressed precise coordinates, missing response times, matched-only mobilisation joins) affect interpretation? (Items P1, P2, P3, P5.)
- **SQ5** — does the dashboard help users notice, compare, and qualify patterns *without overstating* station coverage, routing, or relocation claims? (Items P4, P6.)

Interpretation still draws on the dual-process framework of \cite{padilla2018} and the visual-variable ranking of \cite{maceachren2012}. The *notice / use / explain* rubric operationalises SQ5's "notice, compare, and qualify" directly.

This is **not** a controlled experiment. The probe yields qualitative observations and a small *notice / use / explain* rubric that maps to §6.4 rows.

## Probe Format

Six probe items. Each item is a short verbal prompt, optionally followed by one neutral follow-up if the participant gives a one-word answer. The facilitator records (a) verbatim response and (b) a 0 / 1 / 2 score on the rubric below.

### Notice / Use / Explain Rubric (per item)

- **0 — Did not notice.** The participant did not register the cue without prompting.
- **1 — Noticed.** The participant registered the cue when prompted but did not adjust their interpretation.
- **2 — Used / explained.** The participant noticed the cue *and* qualified at least one Strand-2 conclusion because of it, *or* explained back to the facilitator what the cue meant.

The rubric is observational, not statistical. Score each item independently.

## Probe Items

### P1 — Precise-coordinate-coverage column (ranking table) [SQ4]

**Prompt (read aloud):**
> "In the ranking table at the bottom, there's a column that reports a percentage per borough. Did you notice it during the tasks? What did you take it to mean?"

**§6 anchor:** §6.4 row 1 (precise-coord coverage as the ranking-table 'exposure' half of the §3.3 / §4.4 contract).

**Score-2 example:** participant says "yes, I noticed Westminster's precise-coordinate coverage was lower so I treated its choropleth fill more cautiously."

### P2 — Missing first-pump-time denominator [SQ4]

**Prompt:**
> "The 6-minute exceedance share — for example, '32.4 % of incidents'. Of *which* incidents? Did the dashboard tell you anywhere?"

**Follow-up if needed:**
> "If a borough had a particular month with no recorded response time, do you know what the dashboard does with it?"

**§6 anchor:** §6.4 row 2 (denominator-conditional reading of the headline 32.4 %).

**Score-2 example:** participant correctly identifies that the share is computed only over incidents with a recorded time (278,468 of 293,646), not all incidents.

### P3 — Borough-month cells with no data [SQ4]

> **Protocol note:** the 2024-01–2026-02 slice has **no** empty borough-month-group cell (2,574/2,574 populated, zero null medians, API-verified), so the original "did you encounter a blank panel" wording can never trigger. The prompt is therefore hypothetical; the empty-state banner itself is verified working via forced selection.

**Prompt (hypothetical form):**
> "Suppose you picked a combination of borough, month, and incident group that had no incidents at all in the data. What would you *expect* the dashboard to show you — and would you trust a zero, a blank, or a warning more?"

**§6 anchor:** §6.3 row 1 (empty-state behaviour, verified by forced-selection test), §6.4 row 1.

### P4 — Footprint-scenario disclaimer [SQ5]

> **Protocol note:** the dashboard screen renders **no station-related element** (0 DOM matches; the footprint UI toggle is deferred), so the prompt is two-part: first "dashboard alone", then anchored to the two §6 station figures, which the facilitator shows on paper or a second screen.

**Prompt (amended, two-part):**
> (a) "From this dashboard alone, what — if anything — can you say about fire-station coverage in London?"
> (b) *[Show the §6 station figures: address-vs-footprint shift and borough proximity.]* "These two charts come with the project. Now what would you tell a friend the project can and cannot say about station coverage?"

**§6 anchor:** §6.4 row 3 (whether the assignment-footprint framing lands) + §7.2 (risk of misreading the dashboard as operational dispatch). Expected score-2 on (a) is an explicit "nothing from the dashboard alone".

**Score-2 example:** participant explicitly distinguishes "where the station's incidents historically happened" from "where the building is" and refuses to make a coverage claim.

### P5 — Mobilisation matched-only caveat (interpretive) [SQ4]

**Prompt:**
> "If I told you the underlying mobilisation data has 1,763 cross-boundary records — appliances dispatched outside the 33 London boroughs — would you expect those to be in or out of the borough-level numbers you've been reading?"

**§6 anchor:** §6.4 row 4 (matched-only filter visibility in §6 prose; the dashboard does **not** display these records, but the §6 write-up will name the filter).

**Score-2 example:** participant correctly infers that a borough-level claim should exclude cross-boundary mobilisations and asks how that's enforced.

### P6 — What is missing from the dashboard uncertainty reporting [SQ5, feeds §8.3 future work]

**Prompt:**
> "If the dashboard could show you *one more thing* about how trustworthy each number is, what would you want?"

**§6 anchor:** §6.4 row 3 (second-iteration N5 contract — natural-frequency tooltip phrasing and fuzziness encoding retained as future work).

**No score required** for P6; capture verbatim only. The answer feeds the §8.3 future-work bullet on the second-iteration uncertainty contract.

## Scoring Aggregation

After all six items are administered, the facilitator computes per-participant totals:

- Items P1–P5: each scored 0 / 1 / 2 → range 0–10.
- Item P6: verbatim only, no numeric score.

A participant total is **descriptive**, not a usability index. Use it only for the §6.4 write-up's qualitative banding (e.g., "P02 noticed the precise-coordinate coverage column without prompting; P03 noticed only after probing"). No statistical comparison across participants is in scope.

## Output Format

Append to the same observation-log entry started during Strand 2:

```
## SQ4/SQ5 (was RQ5) Probe — P0X
- P1 (precise-coordinate coverage column):  score / verbatim
- P2 (missing time):     score / verbatim
- P3 (empty cells):      score / verbatim
- P4 (footprint label):  score / verbatim
- P5 (matched-only):     score / verbatim
- P6 (one-more-thing):   verbatim
- P1–P5 total:           sum
```

## Out of Scope

- Inferential analysis across participants. Strand 3 is qualitative.
- Modifying §4.4 N5 second-iteration uncertainty contract (fuzziness encoding, natural-frequency tooltips) during the session — these remain implementation work for the second-iteration UI pass.
- Any prose change to §6.4 during the session.
