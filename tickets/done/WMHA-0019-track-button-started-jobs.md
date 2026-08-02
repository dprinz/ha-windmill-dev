---
id: WMHA-0019
title: Track jobs started through runnable buttons
status: done
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

- [x] A job started by pressing a runnable button is present in the registry immediately afterwards.
- [x] A button-started job can be cancelled through `windmill.cancel` while it is eligible.
- [x] The completion event for a button-started job reports `started_by_home_assistant: true`.
- [x] Registry size and age bounds are unchanged and still enforced on read and write.
- [x] No argument, result or log payload is persisted for a button-started job.
- [x] A regression test covers the button path and fails against the current implementation.

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
| Sharing one start-and-track helper between action and button introduces no import cycle | confirmed | `button.py` imports `async_start_and_track_runnable` from `services.py`; `services.py` imports no entity platform, and the full suite loads both platforms |

## Validation evidence

| Check | Command or inspection | Result |
| --- | --- | --- |
| Repository guardrails | `python scripts/validate_repository.py` | passed (22 tickets checked) |
| Execution and lifecycle tests | `uv run pytest -q tests/test_execution.py tests/test_lifecycle.py` | passed, 35 tests |
| Regression check | Same two files with `button.py` reverted to `async_start_runnable` | failed as required: `test_button_started_job_is_tracked_and_cancellable`, `test_button_started_completion_reports_home_assistant_origin` |
| Full suite and coverage | `uv run pytest -q --cov=custom_components.windmill --cov-report=term-missing --cov-fail-under=95` | passed, 352 tests, 97.02% |
| Lint, format and types | `uv run ruff check custom_components tests`; `uv run ruff format --check custom_components tests`; `uv run mypy custom_components/windmill` | passed |
| Lock and whitespace | `uv lock --check`; `git diff --check` | passed |

## Review evidence

- Reviewer/session: separate review pass inside the implementing session. `AGENTS.md` asks for an
  independent reviewer for medium-risk work; this session was not permitted to spawn a reviewing
  agent, so the deviation is recorded here as it was for `WMHA-0018`.
- Findings: the shared helper reads `kind` and `path` from `resolved.selection` instead of the raw
  action call data. Verified equivalent: `WindmillRunnableCoordinator._async_update_data` keys the
  resolved mapping by `selection.key`, which is `(kind.value, path)` of the same selection, and
  `_async_resolve_runnable` looks the entry up by exactly that key. The stored projection is
  therefore unchanged, and the normalized path is used on both paths.
- Resolution: no change required. The `started_jobs is None` branch remains defensive and untaken in
  tests, as it was before this ticket.

## Residual risks and follow-up

- Frequently pressed buttons consume registry slots faster; the 50-job bound may evict a still
  running job earlier than before. Measure before changing the bound.

## Blog notes

- None
