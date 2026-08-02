# 2026-08-02 — An event fired during bootstrap reaches no automation

- Ticket: WMHA-0023
- Related ADR/research: none
- Publishable: yes

## Initial hypothesis

The fix for completions observed during config-entry setup was supposed to be a one-liner: when the
event entity is added, deliver the pending snapshot through the same guarded update handler as any
listener notification. The assumption was that an event entity may fire at any time and automations
will hear it, because that is what the event entity model suggests.

## What happened

That assumption is wrong during Home Assistant startup — as far as the pinned source shows. An
automation whose entity is set up while Home Assistant is not running does not attach its triggers
at setup time; it listens once for `EVENT_HOMEASSISTANT_STARTED` and attaches them there
(`homeassistant/components/automation/__init__.py`, `_async_enable`, read in the pinned 2026.7.4
source on 2026-08-02). A `state_changed` event fired during bootstrap — exactly when a catch-up
publication of completions observed during setup would run — appears to be processed by nobody. The
event would have been "published" and still lost, recreating the defect one layer down.

The restart case is the one that matters most here: completions that finished while Home Assistant
was down are observed by the setup refresh, and cold start is precisely the situation where the
automation integration may not be listening yet.

## Evidence

Primary source: `_async_enable` in the automation component branches on
`self.hass.state is not CoreState.not_running`; while starting, trigger attachment is deferred to a
one-shot `EVENT_HOMEASSISTANT_STARTED` listener. The fix uses `homeassistant.helpers.start.async_at_started`,
which runs a callback at that event or immediately when Home Assistant is already running (reload).
Regression coverage: a reload whose setup refresh observes a completion fires exactly one event with
the right `job_id`; a failed poll and the recovery afterwards fire none again; a first-ever setup
still fires nothing. Two further tests pin the deferral itself: with `hass.set_state(CoreState.starting)`
nothing fires before `EVENT_HOMEASSISTANT_STARTED` and exactly one event fires after it, and an
unload before that event cancels the delivery without a leftover.

## Decision or correction

The catch-up delivery is scheduled through `async_at_started` and cancelled via `async_on_remove`.
On a reload it fires immediately; on a cold start it fires after startup completed, when automation
triggers should be attached. The delivery itself still goes through the `WMHA-0022` guard, so the
fix adds no second publication path.

## Reusable lesson

"Fired" is not "observed". Any integration that publishes catch-up events — anything that happened
while Home Assistant was down — has to publish them no earlier than `EVENT_HOMEASSISTANT_STARTED`,
or automations silently miss them. `async_at_started` makes the correct timing a one-liner, and the
same helper keeps the reload path immediate.

## Limits

The guarantee basis is internal behavior read in the pinned Home Assistant source (2026.7.4) on
2026-08-02, not a documented public contract: trigger attachment is deferred to
`EVENT_HOMEASSISTANT_STARTED`, and the event bus queues nested fires, so a trigger attached inside
the started-event processing still sees the publication. A trigger attach that is suspended even
once would miss it. A future Home Assistant version could change these internals; the deferral
tests above pin the behavior this integration relies on, but they run against the same pinned
version. Nothing is claimed about other event consumers such as the logbook or Lovelace.

## Redaction checklist

- [x] No secrets or tokens
- [x] No private hostnames or topology
- [x] No personal or production payloads
- [x] Version-sensitive claims include dates and sources
