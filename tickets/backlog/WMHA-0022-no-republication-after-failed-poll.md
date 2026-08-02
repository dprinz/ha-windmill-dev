---
id: WMHA-0022
title: Never republish a completion after a failed run poll
status: backlog
type: quality
priority: medium
risk: medium
created: 2026-08-02
updated: 2026-08-02
depends_on: [WMHA-0007, WMHA-0018]
---

# WMHA-0022: Never republish a completion after a failed run poll

## Outcome

A failed run poll leaves the run event entity alone. Only a successful poll that observed a new
completion may publish an event, so an automation never runs twice for one job.

## Why

The run event entity is the integration's only automation trigger surface, and a duplicated trigger
is indistinguishable from a real second completion. With a 60-second poll interval, one transient
rate limit or network error right after an active minute is enough to fire every automation a second
time. Users would have to make their automations idempotent for a reason that does not exist in the
Windmill data.

## Context

Found during the implementation of `WMHA-0018` on 2026-08-02 and deliberately not fixed there: it is
a distinct defect, and the acceptance criteria of `WMHA-0018` cover only the collapsed publication
and the unsupervised forget task.

`DataUpdateCoordinator` notifies its listeners on a failed refresh as well, and `self.data` then
still holds the snapshot of the last successful poll. `WindmillRunEventEntity`
(`custom_components/windmill/event.py`) reads `self.coordinator.data.new_events` unconditionally, so
the completions of the previous poll are triggered again. `EventEntity._trigger_event` assigns a
fresh `dt_util.utcnow()` timestamp, which is the entity state, so the republication becomes visible
as soon as the entity is available again.

Reproduced against the current implementation: one successful poll publishing a `canceled`
completion at `…:42.660+00:00`, then a `WindmillRateLimitError` poll, then a successful poll with no
new completion, left the entity at `…:42.661+00:00`. No new completion existed, and both the tracked
registry and the aggregate sensors stayed correct, which is why nothing else notices.

The same shape applies to any listener notification that is not a fresh observation.

## Required context

- `AGENTS.md`
- `custom_components/windmill/event.py`
- `custom_components/windmill/coordinator.py` (`WindmillRunCoordinator`, `WindmillRunSnapshot`)
- `tests/test_runs.py`
- `../done/WMHA-0018-run-event-emission-defect.md`

## Requirements

- A listener notification that does not carry a fresh observation publishes no event.
- A completion is published at most once, across failed polls, reloads and restarts.
- Availability handling stays intact: the entity still becomes unavailable on a failed poll and
  recovers afterwards.

## Acceptance criteria

- [ ] A regression test covering "successful poll with a completion, failed poll, successful poll
      without a completion" keeps the entity state unchanged, and fails against the current code.
- [ ] Existing deduplication, ordering, historical-replay and empty-first-poll behavior are
      unchanged.
- [ ] The rate-limit availability test still passes unchanged.

## Non-goals

- Changing the event types, attributes or the retention model.
- Replacing polling with push observation; that stays `WMHA-0016`.

## Constraints

- `EventEntity._trigger_event` is `@final`; the fix belongs in the update handler or in the
  coordinator snapshot, not in a subclassed trigger.

## Assumptions and research needs

| Item | Classification | Validation |
| --- | --- | --- |
| `DataUpdateCoordinator` notifies listeners on failed refreshes | verified | Reproduced on 2026-08-02 against the pinned Home Assistant version |

## Validation evidence

Fill during implementation; do not pre-check.

| Check | Command or inspection | Result |
| --- | --- | --- |
| Repository guardrails | `python scripts/validate_repository.py` | not run |
| Run tests | `uv run pytest -q tests/test_runs.py` | not run |
| Full suite and coverage | `uv run pytest -q --cov=custom_components.windmill --cov-report=term-missing --cov-fail-under=95` | not run |

## Review evidence

- Reviewer/session: not started
- Findings: not started
- Resolution: not started

## Residual risks and follow-up

- A guard on `last_update_success` is the smallest fix, but the durable question is whether a
  snapshot should carry deltas at all. Consider recording the answer in an ADR if the fix changes
  the coordinator contract.

## Blog notes

- Candidate: a coordinator snapshot that carries deltas instead of state republishes them on every
  listener notification, including the ones that observed nothing.
