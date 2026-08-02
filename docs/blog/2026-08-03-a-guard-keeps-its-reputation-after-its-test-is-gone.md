# 2026-08-03 — A guard keeps its reputation after its test is gone

- Ticket: WMHA-0032
- Related ADR/research: `tickets/done/WMHA-0022-no-republication-after-failed-poll.md`, `tickets/done/WMHA-0023-publish-completions-observed-during-setup.md`
- Publishable: yes

## Initial hypothesis

The run event entity guarded publication with two conditions: the coordinator's last poll must have
succeeded, and the snapshot must not be the one already published. The first half was introduced by
a ticket whose evidence table names the test that fails without it. It was therefore assumed to be
load-bearing, and a later ticket accepted a permanent event-loss window rather than touch it,
reasoning that lifting the guard would reintroduce duplicate events.

## What happened

The test named in that evidence table no longer exists. A later ticket replaced it with a
differently named test that asserts the opposite outcome and passes with only the identity check in
place. Deleting the first half left the entire suite green.

Worse than dead weight: the half was the reason for the accepted loss window. A completion observed
by the refresh during config-entry setup waits for `EVENT_HOMEASSISTANT_STARTED` before it is
published. If the one poll in between fails, the failed poll notifies the listeners, the guard
suppresses publication — and when the deferred delivery finally runs, the guard suppresses it again,
because the poll is still marked failed. The completion is dropped forever. A test written to
reproduce this failed on the first attempt with "expected 1 event, got 0".

So the justification for accepting the loss window ("the guard is load-bearing against duplicates")
was false, and the guard's actual effect was to cause the loss it was cited as preventing.

## Evidence

- Mutation: `if not self.coordinator.last_update_success or snapshot is self._published:` reduced to
  the identity check alone — full suite green.
- The pinned `DataUpdateCoordinator` assigns `self.data` only on the success path, so a failed
  refresh cannot replace the snapshot object; identity alone prevents republication.
- `test_failed_poll_before_started_still_delivers_the_setup_completion`, written before the change,
  failed against the unchanged code.

## Decision or correction

The condition was replaced with an explicit "Home Assistant has started" flag, set by the
`async_at_started` callback that already existed. The deferral was worth keeping;
`last_update_success` was simply the wrong way to say it. The loss window closed.

## Reusable lesson

Two lessons, and the second cost more than the first.

A guard's reputation lives in prose — an evidence table, a ticket's justification — while its
meaning lives in a test that a later ticket may rename, replace or delete without noticing what it
was pinning. Only mutation tells you which of the two is current. When a ticket says "removing this
would break X", the cheap check is to remove it and see.

The second: the first attempt to pin the *replacement* guard also passed. The new test could not
discriminate it, because the early publication it was supposed to catch happens while the entity is
unavailable, so its state write is suppressed and the event surfaces later anyway. Writing the
ticket at that point would have repeated the exact failure being corrected — a guard with a test
next to it that does not test it. A second test using a *successful* poll during bootstrap, where
the entity is available and the behaviors differ observably, was needed.

Mutation testing is not a one-shot ritual you perform on the old code. It applies to the code you
just wrote, and it will occasionally tell you that your new test is decoration.

## Limits

The residual was measured, not eliminated: a completion triggered while the entity is unavailable
loses its state write, so a newer completion observed by the recovery poll supersedes it. That is
pinned by its own test and published as a known limitation. Removing it would require queueing
undelivered event lists across snapshots, which duplicates the coordinator's retention model.

The change is covered by unit tests against Home Assistant's public interfaces, not by a live
Home Assistant restart on real hardware.

## Redaction checklist

- [x] No secrets or tokens
- [x] No private hostnames or topology
- [x] No personal or production payloads
- [x] Version-sensitive claims include dates and sources
