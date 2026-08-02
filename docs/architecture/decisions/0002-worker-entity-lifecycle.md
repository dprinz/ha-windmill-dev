# ADR-0002: Worker entities are fixed at config-entry setup

- Status: accepted
- Date: 2026-08-02
- Deciders: project owner through WMHA-0021, implementation and review of WMHA-0006
- Related tickets: WMHA-0006, WMHA-0013, WMHA-0021
- Supersedes: none

## Context

`WMHA-0006` added two optional worker features: per-group sensors (alive workers and distinct
versions) and opt-in per-instance sensors. Both entity sets are built once, during platform setup:

- `custom_components/windmill/__init__.py` reads the configured worker groups once through
  `_async_configured_worker_groups(client)` and passes them to the worker coordinator as
  `known_groups`.
- `custom_components/windmill/sensor.py:54` (`_worker_sensors`) iterates `coordinator.data.groups`
  and `coordinator.data.instances` of the first snapshot and returns that list to
  `async_add_entities`. Nothing adds or removes worker entities afterwards.

Workers are the most volatile objects Windmill exposes. They restart, scale and disappear, and the
worker list is a five-minute liveness window rather than an inventory. An integration that mirrors
that list one-to-one in the entity registry would add and remove entities continuously, which
breaks dashboards, automations, history and the recorder.

`WMHA-0006` chose stability, but recorded neither the choice nor its cost. This ADR records both.

## Decision drivers

- Entity identity must be stable enough for dashboards, automations and long-term statistics.
- A worker that stops pinging is normal operation, not a reason to delete a user's entity.
- Home Assistant users expect a workspace-side change to be visible without a restart, so the cost
  of not adding entities dynamically must be stated, not hidden.
- The integration must not accumulate unbounded permanently-zero entities.

## Considered options

1. Dynamic entity lifecycle: add an entity when a group or instance first appears and remove it when
   it stops reporting.
2. Additive dynamic lifecycle: add new groups and instances at runtime, never remove.
3. Fixed entity set per config-entry setup, refreshed only by a reload. Chosen.

## Decision

Worker-group and worker-instance entities are determined once per config-entry setup and change only
when the entry is reloaded.

Consequences that follow, and that documentation must state:

1. A worker group created in Windmill after setup gets no entity until the entry is reloaded.
2. A worker instance that appears after setup gets no entity until the entry is reloaded.
3. An instance that stops reporting keeps its entity and reports `0`. This is intended: a silent
   worker is the condition a user most wants to alert on, and a deleted entity cannot be alerted on.
4. Option changes need no manual action. The options flow uses `OptionsFlowWithReload`, so enabling
   or disabling a worker feature reloads the entry and rebuilds the entity set. Only workspace-side
   changes require the user to reload the integration.
5. Group entities are pre-seeded from the configured worker groups (`known_groups`), so a configured
   group that currently has no alive worker still reports `0` instead of being missing.

### Identifier stability expectation

Per-instance entities are opt-in and their unique ID is
`<entry_id>_worker_instance_alive_<worker_instance>`. The integration therefore requires
`worker_instance` to be stable across worker restarts for the lifetime of a config entry.

This holds for long-lived hosts and named containers. It is unverified for ephemeral deployments:
if a deployment derives `worker_instance` from a per-container hostname, every restart produces a
new identifier, and — because entities are never removed — each reload would add another
permanently-zero entity while the old ones remain in the registry.

The Windmill worker-group documentation checked on 2026-08-02
(https://www.windmill.dev/docs/core_concepts/worker_groups) documents `WORKER_GROUP` but says
nothing about how `worker_instance` is derived, so this stays an explicitly unvalidated risk rather
than a confirmed defect. The mitigation available today is that the feature is opt-in and off by
default.

## Consequences

### Positive

- No entity churn when workers restart, scale or briefly stop pinging.
- History, statistics and automation references survive normal worker turnover.
- Setup cost is bounded: one worker-group read and one bounded worker page walk.

### Negative

- New groups and instances are invisible until a manual reload.
- A deployment with ephemeral instance identifiers accumulates permanently-zero entities across
  reloads, which the user must delete manually.
- Users cannot distinguish "worker gone" from "worker at zero" without looking at history.

### Risks and mitigations

- Ephemeral identifiers — per-instance entities stay opt-in and off by default; the risk is
  documented for users in `WMHA-0013`. If it turns out to be common, a follow-up ticket for a
  bounded instance allowlist or a dynamic lifecycle is required; this ADR would then be revisited.
- Users mistaking a missing entity for a broken integration — `WMHA-0013` documents the reload
  requirement in the user documentation.

## Validation

- Inspection on 2026-08-02 of `_worker_sensors` and `_async_configured_worker_groups` confirms both
  entity sets are built exactly once per setup.
- `tests/test_workers.py::test_configured_group_without_workers_reports_zero` covers the pre-seeded
  configured groups, and `test_restarted_workers_keep_stable_entities` covers the anti-churn goal.
- `WMHA-0021` added two tests that pin the consequences this ADR documents:
  `test_silent_instance_keeps_its_entity_and_reports_zero` and `test_new_instance_needs_a_reload`.
- No production behavior changed for this ADR; it records the existing implementation.

## Revisit when

- Evidence shows that ephemeral `worker_instance` values are common in real deployments.
- Home Assistant makes dynamic entity addition cheap enough to add groups without a reload while
  keeping removal manual.
- A user-visible repair or diagnostic makes "a new worker group exists but has no entity" actionable
  without documentation.
