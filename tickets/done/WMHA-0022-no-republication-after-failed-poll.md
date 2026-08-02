---
id: WMHA-0022
title: Never republish a completion after a failed run poll
status: done
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

- [x] A regression test covering "successful poll with a completion, failed poll, successful poll
      without a completion" keeps the entity state unchanged, and fails against the current code.
- [x] Existing deduplication, ordering, historical-replay and empty-first-poll behavior are
      unchanged.
- [x] The rate-limit availability test still passes unchanged.

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

| Check | Command or inspection | Result |
| --- | --- | --- |
| Repository guardrails | `python scripts/validate_repository.py` | passed (23 tickets checked) |
| Run tests | `uv run pytest -q tests/test_runs.py` | passed, 19 tests |
| Regression check | Guard disabled entirely; then each half disabled separately | failed as required: no guard fails `test_failed_poll_never_republishes_a_completion`; without the identity check `test_repeated_notification_of_one_snapshot_publishes_once` fails; without the `last_update_success` check `test_failed_poll_publishes_nothing_the_entity_has_not_published` fails |
| Full suite and coverage | `uv run pytest -q --cov=custom_components.windmill --cov-report=term-missing --cov-fail-under=95` | passed, 358 tests, 97.05%; `event.py` at 100% |
| Lint, format and types | `uv run ruff check custom_components tests`; `uv run ruff format --check custom_components tests`; `uv run mypy custom_components/windmill` | passed |
| Lock and whitespace | `uv lock --check`; `git diff --check` | passed |

## Review evidence

- Reviewer/session: separate review pass inside the implementing session; the same deviation from
  the independent-reviewer rule as `WMHA-0018` to `WMHA-0020` applies and is recorded here.
- Findings: three. First, the initial version of the repeated-notification test passed against the
  broken code, because under the frozen test clock a republication carries the identical timestamp
  and is therefore invisible in the entity state; it only discriminates after `freezer.tick(...)`.
  Second, both halves of the guard had to be proven load-bearing separately, because either one
  alone passes the other's test. Third, the `last_update_success` half revealed that completions
  observed by the refresh during config-entry setup are never published at all, since the entity is
  added afterwards and never receives that snapshot.
- Resolution: the test now moves the clock and asserts on captured `state_changed` events; both
  halves of the guard have their own failing-without-it regression test; the setup-refresh gap
  became `WMHA-0023` rather than being fixed here, because it is a lost event rather than a
  duplicated one and needs its own acceptance criteria.

## Residual risks and follow-up

- The durable question — whether a coordinator snapshot should carry deltas at all — is unanswered.
  The fix keeps the coordinator contract, so no ADR was written; the reasoning is in the blog note.
- `WMHA-0023` covers the completions observed during setup.

## Blog notes

- Written: `docs/blog/2026-08-02-a-snapshot-that-carries-deltas-is-published-by-every-listener.md`
