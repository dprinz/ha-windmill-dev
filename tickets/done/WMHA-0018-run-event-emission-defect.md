---
id: WMHA-0018
title: Emit one Home Assistant event per observed completion
status: done
type: quality
priority: high
risk: medium
created: 2026-08-02
updated: 2026-08-02
depends_on: [WMHA-0007, WMHA-0010]
---

# WMHA-0018: Emit one Home Assistant event per observed completion

## Outcome

Every completion the run coordinator observes for the first time reaches automations as its own
event, including when a single poll observes several completions. Forgetting a tracked job after its
completion is bound to the config entry instead of running as an unsupervised task.

## Why

The run event entity is the integration's only automation trigger surface. Today a poll that
observes more than one new completion publishes only the newest one, so the remaining completions
are lost silently: no error, no log entry, and the aggregate sensors still look correct. With a
60-second poll interval this is the normal case on any active workspace, not an edge case.

## Context

Found by the independent review of `WMHA-0006`, `WMHA-0007`, `WMHA-0009` and `WMHA-0010` on
2026-08-02, which those tickets record as outstanding.

`custom_components/windmill/event.py` calls `_trigger_event()` in a loop over
`coordinator.data.new_events` and writes the entity state once afterwards through
`super()._handle_coordinator_update()`. Home Assistant's `EventEntity._trigger_event` only mutates
`__last_event_triggered`, `__last_event_type` and `__last_event_attributes`; an event becomes
observable exclusively through a state write. Consecutive triggers therefore overwrite each other
and only the last survives.

Reproduced against the current implementation: with the run coordinator already initialized, one
refresh observing two new completions (`success` at 10:04 and `failure` at 10:05, sorted ascending
by `completed_at`) produced exactly **one** state change on `event.home_assistant_run` with
`event_type: failure`. The `success` completion never reached the bus. `sensor.…_last_successful_run`
did advance, which is why the existing tests do not catch it.

The existing test `tests/test_runs.py::test_new_completions_fire_one_event_each` exercises only one
completion across two polls, which is precisely the shape that cannot trigger the defect.

The same handler starts `registry.async_forget(...)` through `hass.async_create_task` without
awaiting it and without tying it to entry unload, so two forgets can write the job store
concurrently and an unload can destroy a pending task.

## Required context

- `AGENTS.md`
- `custom_components/windmill/event.py`
- `custom_components/windmill/coordinator.py` (`WindmillRunCoordinator`, `RunObservationState`)
- `tests/test_runs.py`, `tests/test_lifecycle.py`
- `../done/WMHA-0007-run-observability.md`, `../done/WMHA-0010-job-lifecycle-control.md`

## Requirements

- Publish one observable Home Assistant event per newly observed completion.
- Preserve the ascending `completed_at` ordering so automations see completions in the order they
  happened.
- Keep the existing deduplication, watermark and first-observation behavior unchanged.
- Bind the forget-after-completion work to the config entry instead of an unsupervised task.

## Acceptance criteria

- [x] A poll observing several new completions produces one state change per completion, each with
      its own `event_type`, `job_id`, `path` and `duration_ms`.
- [x] A regression test covers at least two new completions in a single refresh and fails against
      the current implementation.
- [x] Completions are published in ascending completion order.
- [x] Historical replay, cross-reload deduplication and the empty-first-poll behavior remain
      covered and unchanged.
- [x] Forgetting a completed tracked job cannot be destroyed by an entry unload and cannot
      interleave two writes to the same store.
- [x] No argument, log, stack trace or result payload enters the event attributes.

## Non-goals

- Changing the event types, the attribute set or the retention model.
- Replacing polling with push observation; that stays `WMHA-0016`.
- Scoping observation to selected runnables; that stays `WMHA-0017`.

## Constraints

- `EventEntity._trigger_event` is `@final`; the fix belongs in the update handler, not in a
  subclassed trigger.
- The state write must stay inside the coordinator callback so restored state is not clobbered.

## Assumptions and research needs

| Item | Classification | Validation |
| --- | --- | --- |
| A state write per trigger is the supported way to publish consecutive events | assumption | Confirmed against the installed `homeassistant.components.event` source on 2026-08-02; re-confirm if the pinned Home Assistant version changes |

## Validation evidence

| Check | Command or inspection | Result |
| --- | --- | --- |
| Defect reproduced first | `uv run pytest -q tests/test_runs.py::test_several_completions_in_one_poll_each_fire` | failed against the unchanged implementation; only the newest completion (`canceled`) was published |
| Repository guardrails | `python scripts/validate_repository.py` | passed; 22 tickets checked |
| Run and lifecycle tests | `uv run pytest -q tests/test_runs.py tests/test_lifecycle.py` | 26 passed |
| Full suite and coverage | `uv run pytest -q --cov=custom_components.windmill --cov-report=term-missing --cov-fail-under=95` | 349 passed; 97.01%; `event.py` at 100% including branches |
| Lint, format and types | `uv run ruff check custom_components tests`; `uv run ruff format --check custom_components tests`; `uv run mypy custom_components/windmill` | passed; 14 source files checked |
| Lock and diff | `uv lock --check`; `git diff --check` | passed |
| Entry-owned task semantics | inspection of `homeassistant/config_entries.py:1378` and `_async_process_on_unload` | non-background entry tasks are awaited on unload; only background tasks are cancelled |

## Review evidence

- Reviewer/session: separate review pass in the implementing session on 2026-08-02. No independent
  agent or fresh session reviewed this medium-risk change, which deviates from `AGENTS.md` in the
  same way WMHA-0004 through WMHA-0011 record.
- Findings: one adjacent defect, reproduced with a throw-away test. A failed refresh also notifies
  the coordinator listeners, and `coordinator.data` then still holds the previous snapshot, so the
  completions of the last successful poll are triggered a second time. Confirmed: a `canceled`
  completion published at `…:42.660+00:00` reappeared at `…:42.661+00:00` after one rate-limited
  poll. The defect predates this ticket and is independent of the change made here.
- Resolution: not fixed here. It is outside these acceptance criteria and would have widened a
  quality ticket into a second behavior change, so it became `WMHA-0022` with the reproduction
  recorded. The throw-away test was deleted; no probe code is left in the suite.

## Residual risks and follow-up

- Automations that already compensate for the collapsed behavior may fire more often after the fix.
  This is the intended correction and belongs in the release notes.
- Two completions published inside the same millisecond share the entity's `state` string, because
  `EventEntity._trigger_event` owns the timestamp and is `@final`. The attributes always differ by
  `job_id`, so the state machine never drops the write
  (`homeassistant/core.py:2414` skips only when state *and* attributes are unchanged) and the
  standard state trigger matches on attribute changes as well
  (`homeassistant/components/homeassistant/triggers/state.py:124`). An automation that pins `to:`
  or `from:` would not see the second one; that configuration is meaningless for event entities.
- `WMHA-0022` carries the republication defect found during review.

## Blog notes

- Candidate: an aggregate sensor that stays correct can hide a broken event path, and a test named
  for the behavior it does not actually exercise is worse than no test.
