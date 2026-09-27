# Usability Testing Protocol — Civic Pathfinder

Goal: validate that first-time citizens (18–55, mixed digital literacy) can
reach a completed government-service roadmap and act on step 1 **without
help**. Feed results into GOVERNMENT_APPROVAL_CHECKLIST (usability evidence).

## Participants

- **N = 8** (5 government-service seekers, 2 ASHA/centre operators,
  1 front-desk staffer); at least 3 participants with ≤ 12th-grade education;
  at least 3 on mobile 4G.
- Recruited from [CHANNEL]; consent form covers screen recording + quote use.
- Incentive: [₹ AMOUNT] + travel.

## Setup

- Moderated remote or in-person session, ≤ 45 min; Android phone or the
  participant's own device; production-like build with demo maps.
- Observer sheet: task code, success/partial/fail, time-on-task, first-error,
  quote, assistance given (0 = none).

## Tasks

| # | Task | Success criterion | Target |
|---|---|---|---|
| T1 | Find the scheme you need (e.g. Udyam registration) | Opens correct roadmap | ≥ 7/8, ≤ 90 s |
| T2 | Read a step: understand what document is needed | Names the required doc unprompted | ≥ 7/8 |
| T3 | Register & consent to the process | Completes signup + consent screen | ≥ 8/8, no help |
| T4 | Mark step 1 in progress, then complete | Progress state visible on return | ≥ 7/8 |
| T5 | Save/open a deep link from a "share" | Returns to exact step | ≥ 6/8 |
| T6 | Switch to हिंदी, redo T1 | Finds same roadmap | ≥ 6/8 |
| T7 | Submit a grievance when a step looks wrong | Reaches confirmation screen | ≥ 6/8 |
| T8 | Recall: what is the next concrete action? | States next action + document | ≥ 7/8 |

## Measures & thresholds

- **Task success (primary):** ≥ 85% across T1–T4.
- **Assistance rate:** ≤ 1/8 participants per task.
- **SUS score:** ≥ 70 (median) on post-session questionnaire.
- **Accessibility spot-check:** 200% zoom usable; contrast pass; keyboard
  focus visible (pairs with frontend axe tests in CI).
- Any T-task < 6/8 ⇒ usability requirement **fails**; file issues, retest
  with 4 fresh participants.

## Cadence

Full study pre-launch; 4-person mini-study after any flow redesign; results
logged in `USABILITY_REPORT.md` (created at first study) with dated quotes.
