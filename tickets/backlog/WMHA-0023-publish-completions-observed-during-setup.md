---
id: WMHA-0023
title: Publish completions observed during config-entry setup
status: backlog
type: quality
priority: medium
risk: medium
created: 2026-08-02
updated: 2026-08-02
depends_on: [WMHA-0007, WMHA-0022]
---

# WMHA-0023: Publish completions observed during config-entry setup

## Outcome

A completion that the run coordinator observes during config-entry setup is published exactly once,
instead of being marked as seen and then silently dropped.

## Why

Every restart and every reload runs one refresh before the entities exist. Completions that Windmill
reports in that refresh are recorded in the retention state, so no later poll will report them
again, and the event entity never sees them. An automation that reacts to run completions therefore
misses everything that finished while Home Assistant was restarting — the window most likely to
contain a completion, because the poll walks the jobs that finished while the integration was down.

## Context

Found while implementing `WMHA-0022` on 2026-08-02.

`CoordinatorEntity.async_added_to_hass` registers the listener but does not invoke
`_handle_coordinator_update`, and `WindmillRunCoordinator.async_config_entry_first_refresh` runs in
`async_setup_entry`, before `async_forward_entry_setups`. The events of that first snapshot are
therefore never delivered to `WindmillRunEventEntity`.

The `WMHA-0022` guard makes this deterministic rather than dependent on whether the next poll fails:
before that ticket, a failed poll would publish those events late, with the timestamp of the
failure. Both outcomes are wrong; this ticket is about the correct one.

Not fixed inside `WMHA-0022`, whose acceptance criteria cover republication only.

## Required context

- `AGENTS.md`
- `custom_components/windmill/__init__.py` (setup order)
- `custom_components/windmill/coordinator.py` (`WindmillRunCoordinator`, `RunObservationState`)
- `custom_components/windmill/event.py`
- `tests/test_runs.py`
- `../done/WMHA-0007-run-observability.md`, `../done/WMHA-0022-no-republication-after-failed-poll.md`

## Requirements

- A completion observed by the setup refresh is published once after the event entity exists.
- Publication order stays ascending by completion time.
- The first observation of a brand-new config entry still replays no history.
- Deduplication across restarts and reloads is unchanged; nothing may be published twice.

## Acceptance criteria

- [ ] A regression test reloads an entry whose setup refresh observes a completion and asserts one
      publication with the right `job_id`, and it fails against the current implementation.
- [ ] A first-ever setup still publishes nothing.
- [ ] No completion is published twice across a restart, a reload and a failed poll.

## Non-goals

- Changing the retention bounds or the event attributes.
- Replaying completions from before the first observation.

## Constraints

- The retention state must stay the single source of truth for what was already seen; a second
  "published" marker would have to be persisted and kept consistent with it.

## Assumptions and research needs

| Item | Classification | Validation |
| --- | --- | --- |
| The pending events can be carried in the snapshot until an entity consumes them, without breaking the "one snapshot per poll" contract | assumption | Design during planning; consider deferring the first refresh instead |

## Validation evidence

Fill during implementation; do not pre-check.

| Check | Command or inspection | Result |
| --- | --- | --- |
| Repository guardrails | `python scripts/validate_repository.py` | not run |
| Run and lifecycle tests | `uv run pytest -q tests/test_runs.py tests/test_lifecycle.py` | not run |
| Full suite and coverage | `uv run pytest -q --cov=custom_components.windmill --cov-report=term-missing --cov-fail-under=95` | not run |

## Review evidence

- Reviewer/session: not started
- Findings: not started
- Resolution: not started

## Residual risks and follow-up

- A fix that publishes at entity-add time changes when automations fire relative to Home Assistant
  startup. Check that it cannot fire before the automation integration is ready.

## Blog notes

- None
