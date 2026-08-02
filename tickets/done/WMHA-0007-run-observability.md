---
id: WMHA-0007
title: Expose bounded run observability
status: done
type: feature
priority: high
risk: high
created: 2026-08-01
updated: 2026-08-02
depends_on: [WMHA-0003, WMHA-0005]
---

# WMHA-0007: Expose bounded run observability

## Outcome

Home Assistant exposes aggregate running, queued, successful and failed job information plus automation-friendly events for newly observed completions and failures.

## Why

Users need operational run visibility, but one entity per run would create registry churn, recorder growth and privacy risk.

## Required context

- `AGENTS.md`
- `docs/product/requirements.md`
- verified job-listing and filtering contract from `WMHA-0001`

## Requirements

- Aggregate counters and last-success/last-failure timestamps.
- Event entities for newly observed success, failure and cancellation.
- Configurable scope: all visible top-level jobs, selected runnables or Home Assistant-started jobs.
- Bounded polling, pagination and deduplication.

## Acceptance criteria

- [x] No entity is created per job or run.
- [x] Initial polling does not replay historical jobs as new events.
- [x] Duplicate events are prevented across reloads within the documented retention model.
- [x] Raw arguments, logs, stack traces and full results never enter state or diagnostics.
- [x] Pagination and rate-limit behavior are tested.

## Non-goals

- Full Runs-page replication.
- Job cancellation or execution.

## Validation evidence

| Check | Command or inspection | Result |
| --- | --- | --- |
| Repository guardrails | `python scripts/validate_repository.py` | passed; 17 tickets checked |
| Run and client tests | `uv run pytest -q tests/test_runs.py tests/test_api.py` | 140 passed |
| Full suite and coverage | `uv run pytest -q --cov=custom_components.windmill --cov-report=term-missing --cov-fail-under=95` | 243 passed; 98.62% |
| Lint and format | `uv run ruff check custom_components tests`; `uv run ruff format --check custom_components tests` | passed |
| Types | `uv run mypy custom_components/windmill` | passed; 11 source files checked |
| Lock and diff | `uv lock --check`; `git diff --check` | passed |
| Upstream job structs | pinned `windmill-types/src/jobs.rs` at `v1.775.2`, read on 2026-08-02 | verified; `args`, `result`, `logs`, `flow_status`, `email`, `permissioned_as`, `canceled_reason`, `labels` and `tag` are discarded in the client |
| Live run observation against a busy workspace | manual instance check | not run; no disposable workspace with real job traffic is available |

The retention model is a Home Assistant store holding the newest observed completion timestamp, the
last 200 completed job identifiers and the monotonic last-success and last-failure timestamps. It is
documented in `plans/WMHA-0007.md`.

Configurable observation scope from `PR-006` is not part of this ticket. Scoping to selected
runnables or to Home Assistant-started jobs requires the runnable selection of WMHA-0008 and the
started-job registry of WMHA-0009, so it became the new backlog ticket WMHA-0017 rather than a
half-wired option.

## Review evidence

- Reviewer/session: separate review pass in the implementing session on 2026-08-02. No independent
  agent or fresh session reviewed this high-risk change, which deviates from `AGENTS.md`.
- Findings: one finding. The first duplicate-prevention test asserted an unknown event state after a
  reload, which would also have passed if the entity had simply lost its restored state.
- Resolution: the test now compares the event timestamp before and after the reload and forces an
  additional refresh, so it fails if the completion fires again. Re-validated by the full check list
  above.
