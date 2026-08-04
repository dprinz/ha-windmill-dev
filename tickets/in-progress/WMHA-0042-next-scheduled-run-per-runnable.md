---
id: WMHA-0042
title: Show the next scheduled run of a selected runnable
status: in-progress
type: feature
priority: medium
risk: medium
created: 2026-08-04
updated: 2026-08-04
depends_on: [WMHA-0040, WMHA-0041]
---

# WMHA-0042: Show the next scheduled run of a selected runnable

## Outcome

A selected runnable that Windmill schedules gains one timestamp entity reporting when it is due to
run next. A selected runnable with no schedule reports no next run instead of a guess, and the
difference is visible to the user.

## Why

"Last run" answers what happened; "next run" is what makes a Windmill job usable in a Home
Assistant automation — waiting for it, warning when it is overdue, or suppressing a manual start
shortly before a scheduled one. It is deliberately split from `WMHA-0041` because its data source
is the one part of the feature the repository cannot currently justify: it may be free, or it may
require reading a new API surface with its own permission and a cron evaluation.

## Required context

- `AGENTS.md`
- the schedules subsection produced by `WMHA-0040`
- `WMHA-0041` and its implementation
- `docs/architecture/decisions/0001-capability-negotiation.md`
- `custom_components/windmill/api.py` (capability probes, `WindmillJob`)
- `custom_components/windmill/coordinator.py`, `sensor.py`, `config_flow.py`

## Requirements

- Use the source `WMHA-0040` recommends: the queued half of the per-runnable read that
  `WMHA-0041` already performs. Add `scheduled_for` to the job projection and derive next run
  from it. No new request, no new endpoint, no capability entry, no cron evaluation.
- A future scheduled run is a queued row whose `scheduled_for` lies ahead of the current time.
  Compare against `homeassistant.util.dt`, never `datetime.now`.
- Where several pending occurrences exist for one path, report the earliest.
- Attach the entity to the per-runnable device introduced by `WMHA-0041` and to the same opt-in
  feature option. Do not add a second toggle.
- A runnable without a schedule, or with a disabled schedule, reports no value. A schedule that
  disappears clears the value instead of freezing the last one.
- Never expose schedule arguments, the schedule owner, or any free-form schedule field.

## Acceptance criteria

- [x] A scheduled runnable reports its next execution as a timestamp. —
      `test_a_scheduled_runnable_reports_its_next_run`
- [x] An unscheduled runnable reports no value while its other detail entities keep working. —
      `test_an_unscheduled_runnable_reports_no_next_run`
- [x] Disabling or deleting the schedule in Windmill clears the value within one refresh cycle. —
      `test_a_disabled_schedule_clears_the_next_run`, and
      `test_a_restart_never_announces_a_stale_next_run` for the restart case
- [x] The entity adds no Windmill request beyond the read `WMHA-0041` already performs. — no
      client method was added; `scheduled_for` was already in the parsed response
- [x] No new runtime dependency was added. — `pyproject.toml` is unchanged
- [x] Nothing beyond the occurrence timestamp is retained from the scheduled row. —
      `WindmillJob.scheduled_for` is the only new field, and it is not persisted
- [x] Tests cover scheduled, unscheduled, disabled and multiple-pending cases. — plus
      `test_the_earliest_of_several_reservations_wins` and
      `test_a_job_waiting_for_a_worker_is_not_a_next_run`

## Non-goals

- Creating, editing, enabling or deleting Windmill schedules.
- A calendar entity or multiple upcoming occurrences.
- Predicting a next run for jobs that have no Windmill schedule at all.

## Constraints

- Read-only towards schedules, without exception.
- The entity must not become a second polling loop when the data is already in a response the
  integration receives.

## Assumptions and research needs

| Item | Classification | Validation |
| --- | --- | --- |
| A usable next-occurrence source exists | **verified 2026-08-04** | `WMHA-0040`: Windmill materializes the next occurrence as a queued job with a future `scheduled_for` |
| Schedule reads are available on Community Edition | **moot** | The schedules API is not used |
| A disabled or deleted schedule loses its pending row | **verified 2026-08-04** | `clear_schedule` is called from `edit_schedule`, `set_enabled` and `delete_schedule` |

## Validation evidence

Fill during implementation; do not pre-check.

Run on 2026-08-04 with `uv run python -VV` reporting CPython 3.14.6.

| Check | Command or inspection | Result |
| --- | --- | --- |
| Repository guardrails | `python scripts/validate_repository.py` | pass — 43 tickets checked |
| Tests and coverage | `uv run pytest -q --cov=custom_components.windmill --cov-report=term-missing --cov-fail-under=95` | 432 passed, 98% total |
| Lint | `uv run ruff check custom_components tests` | pass |
| Format | `uv run ruff format --check custom_components tests` | pass — 32 files |
| Type check | `uv run mypy custom_components/windmill` | pass — 16 source files |
| Translation key parity | recursive key-set comparison of `strings.json` against both translations | identical |
| No new dependency | `git diff pyproject.toml uv.lock` | empty |
| CI on the pushed commit | GitHub Actions on `15deb3e` | 2026-08-04: `Tests, lint and types`, `Repository guardrails` and `Validate HACS and hassfest` all green |


## Review evidence

- Reviewer/session: not yet performed. Medium risk, so `AGENTS.md` asks for an independent
  review in a fresh session before this ticket moves to `done/`. Review it together with
  `WMHA-0041`, whose coordinator it extends.
- Findings: pending review.
- Resolution: pending review.

## Residual risks and follow-up

- **A schedule that fires more often than the refresh interval.** Between two observations the
  reserved slot may already have been consumed and replaced. The sensor then briefly shows the
  slot that just ran rather than the next one. Windmill inserts the successor as part of the
  same completion, so the value corrects itself on the next refresh.
- **`WMHA-0043`** is now more visible: with `scheduled_for` parsed, the fact that the workspace
  aggregate counts reserved slots as queued work is fixable, and the field it needs exists.

## Blog notes

- The server had already computed the answer and stored it. The obvious route to "when does this
  run next" is the schedules API, which returns a cron string — and would have made the
  integration re-implement cron parsing, timezones and DST to recover a timestamp Windmill
  writes into its own queue every time a job finishes. The feature ended up needing one new
  field on a response the integration was already fetching, and no new request at all.
- Not every piece of state deserves to be persisted. Last run, status and duration are history
  and survive a restart. Running and next run are claims about the present; restoring them would
  mean announcing a job that finished and a schedule that was disabled while Home Assistant was
  down. The store deliberately holds only half the model.
