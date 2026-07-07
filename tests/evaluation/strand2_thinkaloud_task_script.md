# Strand 2 — Think-Aloud Task Script

> Status: protocol used for the compact think-aloud evaluation with Participants 1--3.
> Updated: 2026-07-07.
> Owner: facilitator (Joe).  
> Sample: n = 3 voluntary participants. Operational LFB practitioner participation is **out of scope** per §6.5.
> Time budget per session: ≤ 45 min total (5 min intro, 4 × 5–7 min tasks, 5 min SQ4/SQ5 probe via `strand3_rq5_uncertainty_probe.md`, 5 min Lab Questionnaire + debrief).

## Purpose

Closes Strand 2 of §4.6: a small-N think-aloud session producing a per-task observation log plus a Lab Questionnaire (Lam et al.\ \cite{lam2011}). Each task is mapped onto a working sub-question (SQ) of the 2026-07-06 value-led RQ set in `PROJECT_BRIEF.md`, so the §6 prose can quote per-task observations against the row that needs them. The observable of interest is **whether the participant can make and qualify a useful analytical judgement**, not which interface component performs best.

Old RQ labels are retained in parentheses for traceability to the earlier protocol labels.

### RQ remap table (old §1.3 label → working SQ → task)

| Old label | Working sub-question (`PROJECT_BRIEF.md`) | Task |
|---|---|---|
| RQ1 (incident density) | SQ3 demand side + SQ1 slicing mechanics | Task 1 |
| RQ2 (response-time differences) | SQ1 (persistent six-minute exceedance patterns); optional follow-up → SQ2 (workload/mobilisation) | Task 2 |
| RQ3 (representation) | SQ3 (risk-response gap triage judgement) | Task 3 |
| RQ4 (interaction) | SQ5 (qualified comparative judgement) | Task 4 |
| RQ5 (uncertainty cues) | SQ4 + SQ5 | Strand 3 probe |

This is **not** a controlled-task time experiment. The full UP scenario from \cite{lam2011} is explicitly out of scope per §4.6 and §6.5.

## Pre-Session Checklist (Facilitator)

1. Confirm the dashboard is live at `http://127.0.0.1:5057/dashboard` and Strand 1 ran with zero `Blocker` findings.
2. Confirm the participant has read the consent / anonymisation note (`observation_log_template.md` § Consent) and verbally agreed.
3. Allocate a participant ID `P0X` (anonymous; no real name, email, or institutional ID stored).
4. Set viewport to 1440 × 900 desktop. Open a fresh browser window with no extensions.
5. Ensure no audio recording unless the participant explicitly consents in writing; default is facilitator notes only.

## Introduction Script (5 min, verbatim)

> "Thanks for taking part. This is a short usability session for an MSc dissertation visual analytics dashboard for London Fire Brigade incident data. There is no right or wrong answer; I'm interested in how you reason out loud as you use the dashboard. I'll ask you to attempt four short tasks. Please describe what you are looking at, what you are trying to do, and what's confusing as you go. The session is anonymised — no names or emails are recorded. You can stop at any time. Any questions before we start?"

State explicitly that:
- The dashboard is **exploratory**, not an operational dispatch tool.
- Some response-time records are missing in the underlying open data; the dashboard surfaces this honestly.
- The "footprint scenario" is **not** a station-coverage model. Use of the word "coverage" by the participant should be observed but not corrected.

## Task 1 — SQ3 demand side (was RQ1): Where is incident demand highest? (5–7 min)

**Task statement (read aloud):**
> "For one chosen month in 2025 and one incident group, identify which two London boroughs have the highest incident counts. Tell me what you would conclude about those two boroughs from the dashboard alone."

**Expected user actions:**
- Select a 2025 month and one incident group. Do not ask the participant to aggregate a full year or all incident groups in this iteration.
- Read the ranking table or the choropleth fill.
- Cross-check at least one of the two against the trend pane.

**Probes (only if stuck after ≥ 60 s):**
1. "What does each panel show you?"
2. "Is there a panel that ranks boroughs in a list?"
3. "How would you check whether the same borough is high every month or only in one month?"

**§6 anchor:** §6.1 row 1 (borough-month aggregation). §6.1 row 2 (hour × weekday density profile) remains a pipeline/report figure task, not a first-iteration dashboard task. Feeds the demand half of SQ3's risk-response gap reading in Task 3.

**What to record:** which panel(s) the participant used first, whether they noticed the precise-coord-coverage caveat for the boroughs they named, any verbal hesitation about "incident count" vs "incident rate".

## Task 2 — SQ1 (was RQ2): Which boroughs show above-target first-pump attendance times? (5–7 min)

**Task statement (read aloud):**
> "Pick any month in 2025. Find a borough whose median first-pump response time is above the 6-minute target, and a borough whose median is below. Walk me through how you compared them."

**Expected user actions:**
- Filter to a specific month.
- Read the choropleth fill or the ranking table to identify above- and below-target boroughs.
- Hover the choropleth to surface medians or read the table.

**Probes:**
1. "Where do you see the 6-minute target on the dashboard?"
2. "If a borough had no recorded response time for that month, how would you know?"

**§6 anchor:** §6.1 row 1 (borough-month exceedance share), §6.4 row 2 (missing-time hedge — does the participant verbalise the denominator?).

**What to record:** whether the participant's verbal interpretation conflates *incident count* with *response-time exceedance*; whether they spot any month-borough cell with missing data and how they treat it.

**Optional follow-up (if time and momentum, → SQ2):** "If you had appliance-level deployment data — which appliance was sent and from which station — would that change how you read this borough's pattern?" Record verbatim. Maps to SQ2 (workload composition and mobilisation evidence) and §6.1 row 3 (appliance-level deployed-from station distribution); the dashboard does **not** expose this view in this iteration, so the answer is interpretive.

## Task 3 — SQ3 (was RQ3): Risk-response gap triage judgement (5–7 min)

**Task statement (read aloud):**
> "Find a borough-month combination where high incident density coincides with above-target response time. Imagine you had to nominate one borough-month for further investigation by a planning analyst — which would you pick, and what would you want checked before acting on it?"

**Expected user actions:**
- Cross-reference the choropleth (response-time fill) against the trend pane (incident count) or ranking table.
- Sort the ranking table on the exceedance-share column.
- Verbalise the trade-off between "many incidents" and "long response time".
- Reach a **triage judgement** and attach at least one caveat (missing coordinates, small denominator, single-month spike, incident-group mix).

**Probes:**
1. "Could the dashboard show you both at once, or do you have to compare two panels?"
2. "What would make you *less* confident in the combination you picked?"

**§6 anchor:** §6.2 row 4 (ranking table supports the gap reading without forcing the participant to decode the choropleth).

**What to record:** the primary observable is whether the participant produces a **usable, qualified triage judgement** — a named borough-month *plus* a stated caveat — not which panel they used. Secondarily: whether they use the ranking table or the choropleth as their primary source, whether they ask for a bivariate map, whether they spontaneously cite the precise-coord-coverage column.

## Task 4 — SQ5 (was RQ4): Qualified comparative judgement across months (5–7 min)

**Task statement (read aloud):**
> "Compare the same borough across three different months of your choice. At the end, tell me in one or two sentences what you would conclude about that borough's trend — and how sure you are."

**Expected user actions:**
- Brush a borough on the map to lock the selection.
- Sequentially change the month filter, observing the trend pane and distribution pane updating.
- Produce a **comparative conclusion** ("improving / worsening / flat / can't tell") and qualify it (data volume, missing months, incident-group mix).

**Probes:**
1. "If the borough selection were lost when you changed the month, what would you do differently?"
2. "How confident are you in that conclusion — what would change your mind?"

**§6 anchor:** §6.3 row 1 (linked brushing / Connect category), §6.3 row 2 (Filter category preserving the brush).

**What to record:** the primary observable is whether the participant reaches a **correct, appropriately hedged comparative conclusion** — including a legitimate "can't tell from this data". Secondarily: interaction mechanics (was the brush preserved, did they recover from filter loss), any request for the deferred footprint UI toggle (§6.3 row 3), any comment that latency is or is not within their perceptual budget (§6.3 row 4).

## Bridge to Strand 3 (1 min, verbatim)

> "Thanks. Now I'd like to ask you a few quick questions about how you read the dashboard's information about *what's missing or uncertain*."

Hand off to `strand3_rq5_uncertainty_probe.md`.

## Lab Questionnaire (post-Strand 3, 5 min)

After the SQ4/SQ5 probe (was: RQ5 probe), administer the three Lab-Questionnaire items from \cite{lam2011}, each on a 1–5 Likert scale (1 = strongly disagree, 5 = strongly agree):

1. **Clarity.** "The dashboard's panels were easy to read."
2. **Usefulness.** "If I had to investigate a borough's response-time pattern, this dashboard would help me."
3. **Trust.** "I would trust the numbers on this dashboard enough to quote them in a class discussion."

Record each rating as a single integer per participant. Capture any verbal explanation alongside the rating; do not paraphrase.

## Debrief (final 2 min)

Ask the participant:
1. "Was anything about the dashboard misleading?"
2. "Is there anything you'd remove?"

Thank the participant. Confirm again that no PII was stored. Save the observation log entry under the assigned participant ID. Close the browser session and stop the Flask app if no further participant is queued.

## Out of Scope

- Statistical inference. n = 3–5 yields qualitative observations only; §6.5 records this limitation.
- Any change to §6 / §7 / §8 prose during the session. Defects feed §5.6 deviation entries or future commits, not in-session edits.
- Quantitative completion-time measurement (UP scenario; out of scope per §4.6).
