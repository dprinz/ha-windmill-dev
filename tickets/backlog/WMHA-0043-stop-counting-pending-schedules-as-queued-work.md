---
id: WMHA-0043
title: Stop counting pending schedules as queued work
status: backlog
type: bug
priority: medium
risk: low
created: 2026-08-04
updated: 2026-08-04
depends_on: [WMHA-0040]
---

# WMHA-0043: Stop counting pending schedules as queued work

## Outcome

`sensor.*_workspace_queued_jobs` reports jobs that are actually waiting for a worker. A job
that Windmill has merely reserved for a future point in time is not counted as queue depth.

## Why

Found while verifying `WMHA-0040`. Windmill materializes the next occurrence of every enabled
schedule as a real queued job with `scheduled_for` set in the future
([`push_scheduled_job`](https://github.com/windmill-labs/windmill/blob/v1.775.2/backend/windmill-queue/src/schedule.rs#L126-L215)).

`_parse_job` in `custom_components/windmill/api.py` classifies a queued row by `running` alone,
so every such row becomes `JobState.QUEUED`, and `WindmillRunCoordinator._observe` counts it.
A workspace with ten enabled schedules therefore shows a permanent queue depth of ten, and the
number never drops to zero no matter how idle the instance is. A user watching that sensor for
backlog cannot distinguish "five jobs waiting for a worker" from "five schedules exist".

This was not visible before, because nothing in the integration parsed `scheduled_for`.

## Required context

- `AGENTS.md`
- `docs/research/windmill-api-contract.md`, section "The next scheduled run is already a
  queued job"
- `custom_components/windmill/api.py` (`_parse_job`, `WindmillJob`, `JobState`)
- `custom_components/windmill/coordinator.py` (`WindmillRunCoordinator._observe`)
- `tests/test_runs.py`

## Requirements

- Distinguish a job waiting for a worker from a job reserved for the future. `WMHA-0041` adds
  `scheduled_for` to the job projection, so the fact is available.
- Decide whether the future-scheduled jobs disappear from the sensor entirely or become their
  own count. Prefer the smaller change unless a scheduled count has an obvious use.
- Do not change the running count, the completion events or the watermark.

## Acceptance criteria

- [ ] A queued row whose `scheduled_for` lies in the future is not counted as queued work.
- [ ] A queued row with no `scheduled_for`, or one in the past, is still counted.
- [ ] The running count, last-success and last-failure timestamps and the run events are
      unchanged, with tests proving it.
- [ ] The behaviour change is recorded in `CHANGELOG.md`, since a user's automation may depend
      on the old number.

## Non-goals

- Adding a next-run entity. That is `WMHA-0042`.
- Changing how completions are observed or deduplicated.

## Constraints

- Comparison against the current time must use `homeassistant.util.dt`, not `datetime.now`, so
  tests can freeze the clock.

## Assumptions and research needs

| Item | Classification | Validation |
| --- | --- | --- |
| `scheduled_for` is present on every queued row | verified 2026-08-04 | `QJ_FIELDS` at the pinned version |

## Validation evidence

Fill during implementation; do not pre-check.

| Check | Command or inspection | Result |
| --- | --- | --- |
| Repository guardrails | `python scripts/validate_repository.py` | not run |
| Tests | see `docs/development/testing-strategy.md` | not run |

## Review evidence

- Reviewer/session:
- Findings:
- Resolution:

## Residual risks and follow-up

- None recorded

## Blog notes

- None
