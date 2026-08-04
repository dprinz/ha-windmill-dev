---
id: WMHA-0042
title: Show the next scheduled run of a selected runnable
status: ready
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

- [ ] A scheduled runnable reports its next execution as a timestamp.
- [ ] An unscheduled runnable reports no value while its other detail entities keep working.
- [ ] Disabling or deleting the schedule in Windmill clears the value within one refresh cycle.
- [ ] The entity adds no Windmill request beyond the read `WMHA-0041` already performs.
- [ ] No new runtime dependency was added.
- [ ] Nothing beyond the occurrence timestamp is retained from the scheduled row.
- [ ] Tests cover scheduled, unscheduled, disabled and multiple-pending cases.

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

| Check | Command or inspection | Result |
| --- | --- | --- |
| Repository guardrails | `python scripts/validate_repository.py` | not run |
| Tests | see `docs/development/testing-strategy.md` | not run |
| Lint and types | see `docs/development/testing-strategy.md` | not run |

## Review evidence

- Reviewer/session:
- Findings:
- Resolution:

## Residual risks and follow-up

- None recorded

## Blog notes

- None
