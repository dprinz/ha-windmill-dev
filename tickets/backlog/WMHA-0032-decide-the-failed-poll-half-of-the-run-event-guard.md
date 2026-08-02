---
id: WMHA-0032
title: Decide and pin the failed-poll half of the run event guard
status: backlog
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

- [ ] The decision is recorded with the experiment that supports it, not with a restated claim.
- [ ] Mutation check: removing the guard half that the ticket decides to keep makes a named test
      fail; the ticket records the test name and the observed failure.
- [ ] No completion is published twice across a failed poll, a reload and a restart; the existing
      deduplication, ordering, historical-replay and empty-first-poll tests stay green.
- [ ] If the half is removed, a test covers the previously lost case — setup refresh observes a
      completion, a poll fails before `EVENT_HOMEASSISTANT_STARTED`, the completion still reaches
      the bus exactly once.
- [ ] The public limitations document matches the resulting behavior.

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

Fill during implementation; do not pre-check.

| Check | Command or inspection | Result |
| --- | --- | --- |
| Repository guardrails | `python scripts/validate_repository.py` | not run |

## Review evidence

- Reviewer/session:
- Findings:
- Resolution:

## Residual risks and follow-up

- None recorded

## Blog notes

- Candidate: a guard whose regression test was renamed by a later ticket can keep its reputation
  long after it lost its meaning. Mutation, not the evidence table, is what proves a guard load-bearing.
