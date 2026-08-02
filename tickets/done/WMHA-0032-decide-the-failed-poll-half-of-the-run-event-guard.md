---
id: WMHA-0032
title: Decide and pin the failed-poll half of the run event guard
status: done
type: quality
priority: high
risk: medium
created: 2026-08-03
updated: 2026-08-03
depends_on: [WMHA-0022, WMHA-0023]
---

# WMHA-0032: Decide and pin the failed-poll half of the run event guard

## Outcome

The `last_update_success` half of the run event publication guard is either removed, which closes
the startup loss window documented by `WMHA-0023`, or kept with a regression test that fails when
it is removed. Either way its behavior is pinned by a test instead of resting on a claim.

## Why

Found by the review of tickets WMHA-0013 to WMHA-0030 on 2026-08-03.

`custom_components/windmill/event.py:56` guards publication with two conditions:

```python
if not self.coordinator.last_update_success or snapshot is self._published:
```

Removing the `not self.coordinator.last_update_success or` half leaves the entire suite green —
verified on 2026-08-03: 392 passed with only the identity check in place. No test discriminates it.

The half was introduced by `WMHA-0022`, whose validation evidence names
`test_failed_poll_publishes_nothing_the_entity_has_not_published` as the test that fails without it.
That test no longer exists. `WMHA-0023` replaced it with
`test_failed_poll_after_setup_publication_never_republishes`, which asserts the opposite outcome for
setup-observed completions — publication instead of suppression — and passes with the identity check
alone.

This matters beyond stale evidence. `WMHA-0023` accepts a permanent event-loss window (a failed poll
between the setup refresh and `EVENT_HOMEASSISTANT_STARTED` drops the completion forever) and
justifies it with "the guard stays load-bearing (lifting it would reintroduce the `WMHA-0022`
republication defect)". Against the current implementation that justification does not hold:
republication is prevented by `snapshot is self._published`, because a failed refresh leaves
`coordinator.data` pointing at the same snapshot object. As it stands, the half is either dead
weight or a silent event dropper, and nothing in the suite says which.

## Required context

- `AGENTS.md`
- `custom_components/windmill/event.py`
- `custom_components/windmill/coordinator.py` (`WindmillRunCoordinator`, `WindmillRunSnapshot`)
- `tests/test_runs.py`
- `../done/WMHA-0022-no-republication-after-failed-poll.md`
- `../done/WMHA-0023-publish-completions-observed-during-setup.md`
- `docs/product/supported-versions-and-limitations.md` (known limitation 2)

## Requirements

- Establish by experiment whether any listener notification can carry a snapshot that is both
  unpublished and not a fresh observation, other than the pending setup snapshot.
- Decide on that evidence whether the `last_update_success` half stays.
- Whichever way the decision goes, add a test that fails when the chosen behavior is removed.
- Keep the `WMHA-0022` outcome intact: no completion may ever be published twice, across failed
  polls, reloads and restarts.
- If the half is removed, update the startup loss window in
  `docs/product/supported-versions-and-limitations.md` and state what replaces it.

## Acceptance criteria

- [x] The decision is recorded with the experiment that supports it, not with a restated claim.
      (Two experiments below; the decision follows from what they showed.)
- [x] Mutation check: removing the guard half that the ticket decides to keep makes a named test
      fail; the ticket records the test name and the observed failure. (Both halves mutation-checked;
      the first attempt at pinning the new half failed and is recorded.)
- [x] No completion is published twice across a failed poll, a reload and a restart; the existing
      deduplication, ordering, historical-replay and empty-first-poll tests stay green. (395 passed.)
- [x] If the half is removed, a test covers the previously lost case — setup refresh observes a
      completion, a poll fails before `EVENT_HOMEASSISTANT_STARTED`, the completion still reaches
      the bus exactly once. (`test_failed_poll_before_started_still_delivers_the_setup_completion`,
      which failed before the change.)
- [x] The public limitations document matches the resulting behavior. (Known limitation 2 rewritten;
      `docs/research/windmill-push-observation.md` follow-up reference updated.)

## Experiments and decision (2026-08-03)

### Experiment 1 — the half is not load-bearing today

Replacing the guard with `if snapshot is self._published:` and running `uv run pytest -q` gives
**395 passed** (392 before this ticket's tests). No test in the suite discriminates the
`last_update_success` half. The ticket's claim is reproduced.

### Experiment 2 — which notifications can carry an unpublished, non-fresh snapshot

Enumerated against the pinned Home Assistant 2026.7.4 `DataUpdateCoordinator`:

- `self.data` is assigned in exactly two places, `_async_refresh` after a successful
  `_async_update_data()` and `async_set_updated_data`. The failure path never reassigns it.
- A failure streak notifies once: `if not self.last_update_success and not previous_update_success:
  return`.
- This integration calls neither `async_set_updated_data` nor `async_set_update_error` on the run
  coordinator (`grep` over `custom_components/`: no hits).

So for any snapshot the entity already published, `snapshot is self._published` alone blocks
republication. The only notification that can carry an *unpublished* stale snapshot is the one
produced by the refresh during config-entry setup, while the catch-up delivery still waits for
`EVENT_HOMEASSISTANT_STARTED`.

### Experiment 3 — what the half actually did there

`test_failed_poll_before_started_still_delivers_the_setup_completion` was written first and failed
against the unchanged code with `assert 0 == 1`: after `EVENT_HOMEASSISTANT_STARTED` the completion
never reached the bus. The half did not suppress a duplicate; it suppressed the only delivery, and
the catch-up hit the same guard because `last_update_success` was still `False`.

### Decision

**The `last_update_success` half is removed and replaced by an explicit `_started` gate** set by
the existing `async_at_started` callback. Dropping it without a replacement would publish the
pending snapshot during bootstrap, where automations have not attached their triggers
(`docs/blog/2026-08-02-events-fired-during-bootstrap-reach-no-automation.md`); the deferral was the
valuable part, `last_update_success` was the wrong way to express it.

### Mutation checks

| Removed half | Result |
| --- | --- |
| `snapshot is self._published` | **3 failures**: `test_failed_poll_never_republishes_a_completion`, `test_repeated_notification_of_one_snapshot_publishes_once`, `test_failed_poll_after_setup_publication_never_republishes` |
| `not self._started` (first attempt) | **395 passed — not pinned.** The new failed-poll test cannot discriminate it: without the gate the early publication happens while the entity is unavailable, so its state write is suppressed anyway and the event surfaces at recovery either way. |
| `not self._started` (after adding `test_successful_poll_before_started_publishes_nothing_early`) | **1 failure**: that test. It uses a *successful* poll during bootstrap, where the entity is available and the two behaviors differ observably. |

### Measured residual

`test_recovery_completion_supersedes_the_pending_one_while_unavailable` pins what remains: a
completion triggered while the entity is unavailable writes `unavailable` instead of its own state,
so if the recovery poll observes a newer completion, only the newer one becomes visible. Measured,
not assumed. This is strictly better than the previous behavior, where the pending completion was
lost in every case, and it is now the content of known limitation 2.

## Non-goals

- Changing the event types, the attribute set or the retention model.
- Adding a persisted "published" marker; `WMHA-0023` excluded it and that constraint stands unless
  this ticket documents why it must change.
- Editing `WMHA-0022` or `WMHA-0023` in `tickets/done/`, which is append-only.

## Constraints

- `EventEntity._trigger_event` is `@final`; the fix belongs in the update handler or in the
  coordinator snapshot.
- The state write must stay inside the coordinator callback so restored state is not clobbered.

## Assumptions and research needs

| Item | Classification | Validation |
| --- | --- | --- |
| A failed refresh always leaves `coordinator.data` as the identical snapshot object, so the identity check alone prevents republication | verified 2026-08-03 by mutation (392 tests green without the other half) | Re-confirm against the pinned Home Assistant version before relying on it |
| No other code path notifies listeners with an unpublished stale snapshot | unvalidated | Enumerate the notification sources of `DataUpdateCoordinator` in the pinned version |

## Validation evidence

| Check | Command or inspection | Result |
| --- | --- | --- |
| Test suite with coverage | `uv run pytest -q --cov=custom_components.windmill --cov-report=term-missing --cov-fail-under=95` | 2026-08-03: 395 passed, total coverage 97.29% |
| Reproduction before the fix | `uv run pytest -q -k failed_poll_before_started` | 2026-08-03: failed with `assert 0 == 1` — the completion never reached the bus |
| Mutation: identity half | guard reduced to `if not self._started:` | 2026-08-03: 3 failed, 391 passed |
| Mutation: started half | guard reduced to `if snapshot is self._published:` | 2026-08-03: 1 failed (`test_successful_poll_before_started_publishes_nothing_early`), 394 passed |
| Lint | `uv run ruff check custom_components tests` | 2026-08-03: all checks passed |
| Format | `uv run ruff format --check custom_components tests` | 2026-08-03: 31 files already formatted |
| Types | `uv run mypy custom_components/windmill` | 2026-08-03: no issues in 16 source files |
| Repository guardrails | `python scripts/validate_repository.py` | 2026-08-03: passed (34 tickets checked) |
| Whitespace | `git diff --check` | 2026-08-03: exit 0 |

## Review evidence

- Reviewer/session: implementing session (Claude Code `b3e36412`, 2026-08-03). **Deviation from
  `AGENTS.md`:** this is medium-risk work and no independent agent or fresh session reviewed the
  diff; the session was not permitted to spawn a reviewing agent. Recorded in the same way as
  `WMHA-0019`. An independent review of `custom_components/windmill/event.py` and the four
  affected tests is the strongest remaining recommendation.
- Findings: one, found during implementation. The first version of the new test did not pin the
  replacement guard — the mutation still passed 395 tests, because an early publication during a
  failed poll is masked by the entity being unavailable. Writing the ticket as if the test proved
  the guard would have repeated exactly the WMHA-0022 failure this ticket exists to correct.
- Resolution: a second test (`test_successful_poll_before_started_publishes_nothing_early`) uses a
  successful bootstrap poll, where the entity is available and the behaviors differ observably; the
  mutation now fails. Both mutation results are recorded above, including the one that did not work.

## Residual risks and follow-up

- The measured residual (a newer completion at recovery supersedes the pending one's state write)
  is pinned by a test and published as known limitation 2. Removing it would require queueing
  undelivered event lists across snapshots, which duplicates the coordinator's retention model and
  exceeds this ticket's non-goals. No follow-up ticket is opened; a user report of a lost
  completion in that window should open one.
- Publication at `EVENT_HOMEASSISTANT_STARTED` during a failure streak triggers the event while the
  entity is unavailable, so it becomes visible with the next successful poll rather than
  immediately. This is delivery, not loss, and is covered by
  `test_failed_poll_before_started_still_delivers_the_setup_completion`.

## Blog notes

- Written: `docs/blog/2026-08-03-a-guard-keeps-its-reputation-after-its-test-is-gone.md` — a guard
  whose regression test was renamed by a later ticket keeps its reputation long after it lost its
  meaning. Mutation, not the evidence table, is what proves a guard load-bearing.
