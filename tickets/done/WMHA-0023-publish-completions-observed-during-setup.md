---
id: WMHA-0023
title: Publish completions observed during config-entry setup
status: done
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

- [x] A regression test reloads an entry whose setup refresh observes a completion and asserts one
      publication with the right `job_id`, and it fails against the current implementation.
- [x] A first-ever setup still publishes nothing.
- [x] No completion is published twice across a restart, a reload and a failed poll.

## Non-goals

- Changing the retention bounds or the event attributes.
- Replaying completions from before the first observation.

## Constraints

- The retention state must stay the single source of truth for what was already seen; a second
  "published" marker would have to be persisted and kept consistent with it.

## Assumptions and research needs

| Item | Classification | Validation |
| --- | --- | --- |
| The pending events can be carried in the snapshot until an entity consumes them, without breaking the "one snapshot per poll" contract | resolved | Adopted in `plans/WMHA-0023.md`: the setup snapshot is delivered once by identity through the `WMHA-0022` guard; deferring the first refresh was rejected because it changes the `ConfigEntryNotReady` semantics of setup |
| A publication at entity-add time should not fire before automations are listening | assumption on Home Assistant internals | `_async_enable` in the automation component defers trigger attachment to `EVENT_HOMEASSISTANT_STARTED` while Home Assistant is starting — read in the pinned 2026.7.4 source, an internal detail rather than a documented guarantee. The catch-up delivery is therefore scheduled via `homeassistant.helpers.start.async_at_started`, which fires immediately on reload; covered by `test_setup_publication_waits_for_home_assistant_started` and `test_unload_before_started_cancels_the_pending_publication` |

## Validation evidence

| Check | Command or inspection | Result |
| --- | --- | --- |
| Repository guardrails | `python scripts/validate_repository.py` | passed (23 tickets checked) |
| Run and lifecycle tests | `uv run pytest -q tests/test_runs.py tests/test_lifecycle.py` | passed, 33 tests |
| Regression check | `test_setup_refresh_completion_fires_once_after_reload` before the fix | failed as required (0 publications instead of 1) |
| Full suite and coverage | `uv run pytest -q --cov=custom_components.windmill --cov-report=term-missing --cov-fail-under=95` | passed, 377 tests, 97.23%; `event.py` at 100% |
| Lint, format and types | `uv run ruff check custom_components tests`; `uv run ruff format --check custom_components tests`; `uv run mypy custom_components/windmill` | passed |
| Lock and whitespace | `uv lock --check`; `git diff --check` | passed |

## Review evidence

- Reviewer/session: independent review agent (separate session), verdict "changes requested"
- Findings: three, no design objection. (1, minor, binding) The deferral path was untested because
  the test harness runs with `hass.state = CoreState.running`, so `async_at_started` fired
  immediately in every test. (2, minor, binding) An undocumented loss window: setup refresh
  observes a completion, the catch-up is scheduled, one poll fails before
  `EVENT_HOMEASSISTANT_STARTED`, the `last_update_success` guard skips the catch-up and the
  retention state has already recorded the completion — it is dropped permanently. Confirmed
  empirically by the reviewer. (3, note) The cold-start safety was overstated as "verified": it
  rests on Home Assistant internals (deferred trigger attachment, event bus queueing nested fires),
  not on a documented guarantee.
- Resolution: (1) `test_setup_publication_waits_for_home_assistant_started` and
  `test_unload_before_started_cancels_the_pending_publication` added; both fail-safe paths pinned.
  (2) Documented under "Residual risks and follow-up"; the guard stays unchanged because lifting it
  would reintroduce the `WMHA-0022` republication defect, and closing the window would require the
  persisted "published" marker this ticket's constraints exclude. (3) Ticket, blog note and README
  reworded to name the assumption and its basis instead of claiming verification.

## Residual risks and follow-up

- The ticket's residual risk — a publication at entity-add time firing before the automation
  integration is ready — is real and addressed by design: during startup automations attach their
  triggers only at `EVENT_HOMEASSISTANT_STARTED`, so the catch-up delivery is scheduled through
  `async_at_started`. On reload Home Assistant is already running and publication is immediate.
  Evidence and reasoning: `docs/blog/2026-08-02-events-fired-during-bootstrap-reach-no-automation.md`.
- Between entity add and `EVENT_HOMEASSISTANT_STARTED` a scheduled poll can publish first; both
  paths share the identity guard, so no completion can fire twice. The pending events then publish
  with the poll's timestamp instead of at startup — observable only as timing, not as loss or
  duplication.
- A failed poll inside the deferral window drops the completion permanently: the setup refresh
  observes a completion, the catch-up is scheduled, and if one poll fails before
  `EVENT_HOMEASSISTANT_STARTED` fires, the `last_update_success` guard skips the catch-up — the
  stale snapshot still carries the events, and the retention state has already recorded them, so no
  later poll reports them again. The window is one poll interval during startup and was confirmed
  empirically during review. The guard stays load-bearing (lifting it would reintroduce the
  `WMHA-0022` republication defect); closing the window would need a persisted "published" marker,
  which the constraints of this ticket exclude. Accepted as a narrow, documented loss window.
- The cold-start safety rests on Home Assistant internals observed in the pinned 2026.7.4 source:
  trigger attachment is deferred to `EVENT_HOMEASSISTANT_STARTED`, and the event bus queues nested
  fires. A trigger attach that is suspended once would miss the publication. This is not a public
  API guarantee; a future Home Assistant version could change it. The two cold-start tests pin the
  behavior this integration relies on.

## Blog notes

- Written: `docs/blog/2026-08-02-events-fired-during-bootstrap-reach-no-automation.md`
