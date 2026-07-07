# Observation Log Template

> Status: local logging template used for the compact think-aloud evaluation.
> Updated: 2026-07-07.
> Owner: facilitator (Joe).  
> Format: one local `.md` file per session, named `session_P0X_YYYYMMDD.md`, stored outside committed project artefacts.

## Anonymisation and Consent

These rules govern every Strand-1, Strand-2, and Strand-3 record:

1. **No personally-identifiable information is stored.** Use anonymous IDs `P01`, `P02`, ... allocated in order of recruitment. Do not store real names, email addresses, KCL student IDs, or social-media handles in any committed file.
2. **No audio recording by default.** Facilitator notes and verbatim short quotes only. If a participant *explicitly* consents to audio recording in writing (paper sign-off, scanned and stored locally outside the repository), the recording is transcribed within 7 days and the audio file is deleted; only the anonymised transcript enters this log.
3. **Demographics captured only as bounded categories.** Years of coding experience as `<2 / 2–5 / 5+`; urban-data familiarity as `none / some / strong`. Do not record degree programme, specific employer, or geographic origin.
4. **Right to withdraw.** A participant can withdraw at any time, including after the session; if they do, the corresponding session log file is deleted and any aggregate note is updated anonymously.
5. **No PII in evaluation records.** Cross-references use the anonymous ID only.

The consent script is verbal:

> "This is a 30–45 minute usability session for an MSc dissertation. I'll take notes. No names or emails are stored. You can stop at any time. Are you happy to continue?"

Record verbal consent as a yes/no in the session metadata block below; do **not** store the participant's spoken-consent words verbatim.

## Per-Session Template

Copy the block below verbatim into a new local file under `tests/evaluation/sessions/session_P0X_YYYYMMDD.md` and complete each field during the session. Do not commit the completed session file; only commit protocol templates and non-identifying aggregate summaries.

```markdown
# Session Log — P0X — YYYY-MM-DD

## Metadata

- Participant ID: P0X
- Date / start time: YYYY-MM-DD HH:MM
- Duration: __ min
- Facilitator: Joe
- Verbal consent obtained: yes / no
- Audio recording: no / yes (with written sign-off; deleted post-transcription)
- Browser + viewport: e.g. Chrome 138 / 1440x900 desktop
- Commit SHA at session start: ____
- Years of coding experience: <2 / 2–5 / 5+
- Urban-data familiarity: none / some / strong

## Strand 1 — Heuristic Walk-Through (facilitator-only, conducted before participant arrives)

Reference: `strand1_heuristic_walkthrough_checklist.md`. Record verdict + severity per heuristic ID.

| ID | Verdict | Severity | One-line note |
|---|---|---|---|
| E1 | pass / fail / n/a |  |  |
| E2 |  |  |  |
| E3 |  |  |  |
| E4 |  |  |  |
| C1 |  |  |  |
| C2 |  |  |  |
| C3 |  |  |  |
| C4 |  |  |  |
| C5 |  |  |  |
| A1 |  |  |  |
| A2 |  |  |  |
| A3 |  |  |  |
| A4 |  |  |  |
| F1 |  |  |  |
| F2 |  |  |  |
| F3 |  |  |  |
| F4 |  |  |  |
| F5 |  |  |  |

Blocker findings (must be fixed before participant Strand-2 sessions begin):

- (none) / (list)

## Strand 2 — Think-Aloud Tasks

Reference: `strand2_thinkaloud_task_script.md`.

### Task 1 — SQ3 demand side, was RQ1 (highest incident demand)

- Completed: yes / partial / no
- Time: __ min
- First panel used: ranking / choropleth / trend / distribution / other
- Verbatim quote(s):
- Friction observed:
- §6 anchor: §6.1 row 1, §6.1 row 2

### Task 2 — SQ1, was RQ2 (above- vs below-target borough)

- Completed: yes / partial / no
- Time: __ min
- Used 6-min target reference: yes / no / unclear
- Noticed missing-time cells: yes / no / not encountered
- Verbatim quote(s):
- §6 anchor: §6.1 row 1, §6.4 row 2
- Optional appliance-level interpretive answer (if asked): verbatim

### Task 3 — SQ3, was RQ3 (risk-response gap triage judgement + caveat)

- Completed: yes / partial / no
- Time: __ min
- Primary source: ranking table / choropleth / both / other
- Asked for bivariate map: yes / no
- Cited precise-coordinate coverage spontaneously: yes / no
- Verbatim quote(s):
- §6 anchor: §6.2 row 4

### Task 4 — SQ5, was RQ4 (qualified comparative conclusion across three months)

- Completed: yes / partial / no
- Time: __ min
- Brushed borough preserved across month changes: yes / no / unclear
- Latency comments: verbatim
- Requested deferred footprint UI toggle: yes / no
- Verbatim quote(s):
- §6 anchor: §6.3 row 1, §6.3 row 2, §6.3 row 4

## Strand 3 — SQ4/SQ5 (was RQ5) Probe

Reference: `strand3_rq5_uncertainty_probe.md`.

| Item | Score (0/1/2) | Verbatim |
|---|---|---|
| P1 — precise-coordinate coverage column |  |  |
| P2 — missing time |  |  |
| P3 — empty cells |  |  |
| P4 — footprint label |  |  |
| P5 — matched-only |  |  |
| P6 — one-more-thing | (verbatim only) |  |

P1–P5 total (descriptive only, not a usability index): __ / 10

## Lab Questionnaire (Lam et al., post-Strand-3)

| Item | Rating (1–5) | Verbatim if any |
|---|---|---|
| Clarity — "panels were easy to read" |  |  |
| Usefulness — "would help me investigate a borough" |  |  |
| Trust — "would quote in a class discussion" |  |  |

## Debrief

- Anything misleading: verbatim
- Anything to remove: verbatim

## Facilitator Reflection (post-session, ≤ 60 s of writing)

- Headline takeaway in one sentence:
- Defect to feed §5.6 deviation list (if any):
- Defect to feed the local evaluation decision note (if any):
- Recovery before the next session (if any):
```

## After Each Session — Facilitator Tasks

1. Save the completed local file under `tests/evaluation/sessions/session_P0X_YYYYMMDD.md`.
2. If any defect is severity `Blocker` or `Major`, record a single local decision entry without pasting the full session log. Reference the session file by anonymous ID and date only.
3. If a participant withdraws, delete their session file and update any aggregate note anonymously.
4. Do **not** edit §6 / §7 / §8 prose during this iteration; observations carry into the prose back-write only after evaluation runs are complete.

## Out of Scope

- Storing personally-identifiable information of any kind.
- Audio recording without written consent.
- Computing aggregate statistics across participants — n = 3–5 yields qualitative observations only, per §4.6 / §6.5.
- Sharing full session files outside the local machine. Even anonymised logs should not be pushed; commit only templates, aggregate summaries, and non-identifying durable decisions.
