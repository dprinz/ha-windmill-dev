# 2026-08-02 — A correct aggregate can hide a broken event path

- Ticket: WMHA-0018
- Related ADR/research: none
- Publishable: yes

## Initial hypothesis

Polling for job completions and turning each newly observed one into a Home Assistant event looked
finished and tested. A test called `test_new_completions_fire_one_event_each` existed, the
last-success and last-failure sensors always matched the workspace, and no error or warning ever
appeared in the log.

## What happened

A poll that observed more than one new completion published only the newest one. Home Assistant's
`EventEntity._trigger_event` assigns three private attributes and nothing else; an event becomes
observable only when the entity state is written. The handler triggered in a loop and wrote the
state once at the end, so every completion except the last was overwritten before it could be seen.

The aggregate sensors were derived from the same retention state, not from the published events, so
they stayed correct throughout. The existing test exercised one completion across two polls — the
one shape in which the defect cannot appear. At a 60-second poll interval, several completions per
poll is the normal case on an active workspace.

## Evidence

A regression test sets up an idle workspace, then lets one refresh observe three completions at
10:01, 10:02 and 10:03 and collects every `state_changed` event for the run entity. Against the
unchanged implementation it recorded exactly one publication, `canceled`, the newest of the three.
After writing the state once per triggered completion it records all three, oldest first, each with
its own `event_type`, `job_id`, `path` and `duration_ms`.

The same review pass also reproduced a second, independent defect: because a `DataUpdateCoordinator`
notifies its listeners on failed refreshes too, and `coordinator.data` then still holds the previous
snapshot, a failed poll republished the completions of the last successful one. That went to its own
ticket rather than into this fix.

## Decision or correction

The update handler now writes the entity state once per triggered completion. Forgetting the tracked
jobs of a poll moved from one unsupervised `hass.async_create_task` per job to a single task created
on the config entry, and the job registry serializes its mutations with one lock, so an unload waits
for that work instead of destroying it and two writes to the same store cannot interleave.

## Reusable lesson

A test whose name describes the behavior it does not actually exercise is worse than no test,
because it removes the suspicion that would otherwise lead someone to look. When a feature has two
derivations of the same source — here an aggregate and an event stream — a correct aggregate is not
evidence about the event stream. Bursts are the interesting case for anything that polls: write the
test for "several at once" before the test for "one, twice".

## Limits

The evidence covers the pinned Home Assistant version in the test environment on 2026-08-02, where
`_trigger_event` is `@final` and the state write is the only publication mechanism. It says nothing
about push-based observation, which is still an open ticket, and it does not prove that two
completions published within the same millisecond are distinguishable by state value alone — they
are distinguishable only by their attributes.

## Redaction checklist

- [x] No secrets or tokens
- [x] No private hostnames or topology
- [x] No personal or production payloads
- [x] Version-sensitive claims include dates and sources
