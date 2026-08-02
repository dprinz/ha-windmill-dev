---
id: WMHA-0019
title: Track jobs started through runnable buttons
status: backlog
type: quality
priority: medium
risk: medium
created: 2026-08-02
updated: 2026-08-02
depends_on: [WMHA-0009, WMHA-0010]
---

# WMHA-0019: Track jobs started through runnable buttons

## Outcome

Every job that Home Assistant starts enters the bounded started-job registry, regardless of whether
the `windmill.run` action or an optional runnable button started it. Button-started jobs are
therefore cancellable and are reported as Home Assistant-started in lifecycle events.

## Why

`WMHA-0010` states the outcome as "Jobs started through Home Assistant are tracked until completion
or expiry". The button is unambiguously a Home Assistant start path, but it is the one path that
does not track. The result is an inconsistency users cannot predict: the same runnable is
cancellable when started by an automation and not cancellable when started by its button on a
dashboard.

## Context

Found by the independent review of `WMHA-0006`, `WMHA-0007`, `WMHA-0009` and `WMHA-0010` on
2026-08-02.

`custom_components/windmill/services.py` records the returned identifier via
`registry.async_track(...)` after `async_start_runnable`. `custom_components/windmill/button.py`
calls the same `async_start_runnable` helper but discards the return value; its docstring states
"Start the runnable asynchronously and discard the job identifier".

Reproduced against the current implementation: after a successful press of
`button.home_assistant_run_u_automation_lights`, `entry.runtime_data.started_jobs.get(job_id)`
returned `None`. Two consequences follow — `windmill.cancel` refuses the job with `job_not_tracked`,
and its completion event carries `started_by_home_assistant: false`.

The `WMHA-0010` acceptance criterion "Only Home Assistant-started jobs enter the local registry" is
still satisfied; it is the converse direction that is not.

## Required context

- `AGENTS.md`
- `custom_components/windmill/button.py`
- `custom_components/windmill/services.py` (`async_run`, `async_start_runnable`)
- `custom_components/windmill/coordinator.py` (`StartedJobRegistry`, `TrackedJob`)
- `tests/test_execution.py`, `tests/test_lifecycle.py`
- `../done/WMHA-0009-runnable-execution.md`, `../done/WMHA-0010-job-lifecycle-control.md`

## Requirements

- Record button-started jobs in the same bounded registry the action uses, with the same metadata
  projection (identifier, kind, path, start time).
- Keep tracking on one shared code path so a future third start path cannot silently skip it.
- Preserve the existing size and age bounds and the metadata-only rule.
- Keep a tracking failure from masking the fact that the job did start.

## Acceptance criteria

- [ ] A job started by pressing a runnable button is present in the registry immediately afterwards.
- [ ] A button-started job can be cancelled through `windmill.cancel` while it is eligible.
- [ ] The completion event for a button-started job reports `started_by_home_assistant: true`.
- [ ] Registry size and age bounds are unchanged and still enforced on read and write.
- [ ] No argument, result or log payload is persisted for a button-started job.
- [ ] A regression test covers the button path and fails against the current implementation.

## Non-goals

- Adding buttons for runnables that take arguments.
- Making buttons return or expose the job identifier in entity state.
- Changing the retention bounds agreed in `WMHA-0010`.

## Constraints

- Buttons stay opt-in and remain limited to selected parameterless runnables.
- Tracking must not turn a successful start into a user-visible failure; the job is already running
  by then.

## Assumptions and research needs

| Item | Classification | Validation |
| --- | --- | --- |
| Sharing one start-and-track helper between action and button introduces no import cycle | assumption | Verify during implementation; `button.py` already imports from `services.py` |

## Validation evidence

Fill during implementation; do not pre-check.

| Check | Command or inspection | Result |
| --- | --- | --- |
| Repository guardrails | `python scripts/validate_repository.py` | not run |
| Execution and lifecycle tests | `uv run pytest -q tests/test_execution.py tests/test_lifecycle.py` | not run |
| Full suite and coverage | `uv run pytest -q --cov=custom_components.windmill --cov-report=term-missing --cov-fail-under=95` | not run |
| Lint, format and types | `uv run ruff check custom_components tests`; `uv run ruff format --check custom_components tests`; `uv run mypy custom_components/windmill` | not run |

## Review evidence

- Reviewer/session: not started
- Findings: not started
- Resolution: not started

## Residual risks and follow-up

- Frequently pressed buttons consume registry slots faster; the 50-job bound may evict a still
  running job earlier than before. Measure before changing the bound.

## Blog notes

- None
