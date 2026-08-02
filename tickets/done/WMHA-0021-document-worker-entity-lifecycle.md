---
id: WMHA-0021
title: Document the worker entity lifecycle trade-off
status: done
type: documentation
priority: low
risk: low
created: 2026-08-02
updated: 2026-08-02
depends_on: [WMHA-0006]
---

# WMHA-0021: Document the worker entity lifecycle trade-off

## Outcome

The decision that worker-group and worker-instance entities are fixed at config-entry setup is
written down, together with what a user must do when a new worker group or instance appears and what
identifier stability the per-instance entities actually require.

## Why

`WMHA-0006` deliberately chose stability over dynamic entity management: entities never churn when
workers restart. The cost of that choice is real but currently undocumented, so the next agent
cannot tell an intentional trade-off from an oversight, and users cannot tell a missing entity from
a broken integration.

## Context

Found by the independent review of `WMHA-0006`, `WMHA-0007`, `WMHA-0009` and `WMHA-0010` on
2026-08-02. This is a documentation gap, not a defect: the behavior is a defensible design choice
that no ticket, plan or ADR records.

Confirmed by inspection:

- `custom_components/windmill/sensor.py` builds worker entities once during platform setup by
  iterating `coordinator.data.groups` and `coordinator.data.instances`.
- `custom_components/windmill/__init__.py` reads the configured worker groups once via
  `_async_configured_worker_groups(client)` when the entry is set up.

Consequences worth recording:

1. A worker group configured in Windmill after setup gets no entity until the entry is reloaded.
2. A worker instance that appears later gets no entity until the entry is reloaded.
3. An instance that stops reporting keeps its entity and reports `0` rather than disappearing, which
   is the intended anti-churn behavior.
4. Changing integration options reloads the entry through `OptionsFlowWithReload`, so option changes
   are already covered; only workspace-side changes need a manual reload.

The `WMHA-0006` requirement "Individual worker entities only with stable identifiers and explicit
opt-in" deserves a second look in this light. Instance identifiers are stable for long-lived hosts,
but Kubernetes pods and ephemeral containers can produce a new identifier on every restart, which
would accumulate permanently-zero entities. Whether that is acceptable, or whether the opt-in needs
a stronger warning, is the open question this ticket should settle.

## Required context

- `AGENTS.md`
- `../done/WMHA-0006-worker-observability.md`
- `plans/WMHA-0006.md`
- `docs/architecture/overview.md`
- `custom_components/windmill/sensor.py`, `custom_components/windmill/__init__.py`

## Requirements

- Record the setup-time entity construction and the reload requirement where the next agent will
  find it, not only in this ticket.
- State explicitly which changes need a reload and which do not.
- Record the identifier-stability expectation for opt-in per-instance entities, including the
  ephemeral-hostname case.
- Decide whether the trade-off is durable enough for an ADR or belongs in scoped documentation.

## Acceptance criteria

- [x] The trade-off, its rationale and the reload requirement are documented in a location named by
      `docs/context-map.md`.
- [x] The documentation states which workspace-side changes require a reload.
- [x] The identifier-stability expectation for per-instance entities is explicit, including the
      ephemeral-identifier risk.
- [x] The decision on ADR versus scoped documentation is recorded with its reason.
- [x] User-facing guidance is either included or handed to `WMHA-0013` by an explicit reference.

## Non-goals

- Implementing dynamic entity addition or removal for worker groups and instances.
- Changing the current anti-churn behavior or the `0` state for silent instances.
- Rewriting the accepted `WMHA-0006` acceptance criteria; corrections need their own ticket.

## Constraints

- `tickets/done/` is append-only, so `WMHA-0006` must not be edited by this ticket.
- Documentation must not imply behavior the code does not have.

## Assumptions and research needs

| Item | Classification | Validation |
| --- | --- | --- |
| Ephemeral worker identifiers occur in realistic Windmill deployments | unvalidated risk | The Windmill worker-group documentation, checked 2026-08-02, documents `WORKER_GROUP` but says nothing about how `worker_instance` is derived. Recorded in ADR-0002 as an unvalidated risk, mitigated by the feature staying opt-in and off by default |
| Dynamic entity addition is not wanted before v1 | assumption | Unchanged: no requirement in `docs/product/requirements.md` and no `WMHA-0015` criterion asks for it, and this ticket's non-goals forbid implementing it |

## Validation evidence

| Check | Command or inspection | Result |
| --- | --- | --- |
| Repository guardrails | `python scripts/validate_repository.py` | passed (23 tickets checked), local links resolve |
| Documentation review | Inspection of `_worker_sensors`, `_async_configured_worker_groups`, `WindmillWorkerInstanceSensor.native_value` and `WindmillWorkerGroupSensor.native_value` against every claim in ADR-0002 | every documented consequence matches the code |
| Worker tests | `uv run pytest -q tests/test_workers.py` | passed, 17 tests |
| Full suite and coverage | `uv run pytest -q --cov=custom_components.windmill --cov-report=term-missing --cov-fail-under=95` | passed, 360 tests, 97.05% |
| Lint, format and types | `uv run ruff check custom_components tests`; `uv run ruff format --check custom_components tests`; `uv run mypy custom_components/windmill` | passed |

## Review evidence

- Reviewer/session: separate review pass inside the implementing session; the same deviation from
  the independent-reviewer rule as `WMHA-0018` to `WMHA-0022` applies.
- Findings: two of the four consequences this ADR documents had no test. The `0` state of a fully
  silent instance was only covered indirectly, by a test that reduced an instance from two workers
  to one, and the reload requirement for a newly appeared instance was not covered at all. A
  documentation ticket that states behavior nobody tests is exactly the failure mode the ticket's
  own constraint warns about.
- Resolution: added `test_silent_instance_keeps_its_entity_and_reports_zero` and
  `test_new_instance_needs_a_reload`. No production code changed.

## Residual risks and follow-up

- If the ephemeral-identifier case turns out to be common, a follow-up ticket for a dynamic entity
  lifecycle or a bounded instance allowlist will be needed. ADR-0002 names this in "Revisit when".
- User-facing wording is handed to `WMHA-0013`, which now carries the requirement.

## Blog notes

- Not written. The observation — "no registry churn" and "reflects reality" are competing goals — is
  real, but it is fully captured by ADR-0002 and would duplicate it rather than add evidence.
