# 2026-08-02 — A snapshot that carries deltas is republished by every notification

- Ticket: WMHA-0022
- Related ADR/research: none
- Publishable: yes

## Initial hypothesis

The run coordinator polls Windmill, computes which completions are new, and hands the entities one
immutable snapshot that contains both the aggregates and the list of new completions. That looked
like a clean separation: the coordinator decides what is new, the entity only publishes. Failure
handling seemed orthogonal, because `DataUpdateCoordinator` already marks entities unavailable when
a refresh fails.

## What happened

A failed refresh notifies the listeners as well, and `coordinator.data` still holds the snapshot of
the last successful poll. The event entity read `coordinator.data.new_events` unconditionally, so
the completions of the previous poll were triggered a second time. `EventEntity._trigger_event`
assigns a fresh `dt_util.utcnow()` timestamp, and that timestamp is the entity state, so the
republication became visible as soon as the entity was available again — as a second trigger for
every automation listening to it.

Nothing else noticed. The aggregate sensors are derived from the retention state rather than from
the snapshot deltas, the started-job registry was already correct, and no log line appeared. With a
60-second poll interval, a single transient rate limit after an active minute is enough.

## Evidence

Two regression tests, each failing against a different half of the fix. The first polls a
completion, then a `WindmillRateLimitError`, then a poll with nothing new, and asserts the trigger
timestamp did not move; it fails when the entity may republish a snapshot it already published. The
second reloads an entry whose setup refresh observed a completion, then fails one poll: the stale
snapshot then carries events the entity has never published, and only the `last_update_success`
check suppresses them.

Writing the second test also produced a measurement worth recording: under frozen test time, a
republication is invisible in the entity state, because the republished trigger gets the identical
timestamp. The first version of the test passed against the broken code. It only discriminates after
`freezer.tick(...)` or by capturing `state_changed` events.

## Decision or correction

The event entity publishes only for a fresh observation: it skips when the last refresh failed and
when the snapshot object is the one it already published, and it still delegates to the coordinator
entity so availability handling is untouched. The coordinator contract is unchanged, so no ADR.

The second test also exposed a separate gap: completions observed by the refresh during config-entry
setup are never published, because the entity is added afterwards and the listener is never called
for that snapshot. Before this fix, a later failed poll would publish them late; now they are
dropped deterministically. That went to `WMHA-0023` instead of being smuggled into this fix.

## Reusable lesson

A snapshot that carries state can be re-read safely; a snapshot that carries deltas cannot. Once the
same object can reach a consumer more than once, "what is new" has to be answered per consumer, not
per producer — either by the consumer remembering what it consumed, or by the delta being consumed
destructively. Any framework that notifies listeners on failure, retry or resubscription turns this
from a theoretical concern into the default path.

The second lesson is about the test harness: a frozen clock hides every defect whose only symptom is
a changed timestamp. If the observable under test is a time, the test has to move time or assert on
events instead.

## Limits

The evidence covers the pinned Home Assistant version in the test environment on 2026-08-02. It
shows that failed refreshes notify listeners; it does not enumerate every other notification path,
which is why the fix also guards on snapshot identity rather than only on the failure flag. It says
nothing about push-based observation, which remains `WMHA-0016`.

## Redaction checklist

- [x] No secrets or tokens
- [x] No private hostnames or topology
- [x] No personal or production payloads
- [x] Version-sensitive claims include dates and sources
