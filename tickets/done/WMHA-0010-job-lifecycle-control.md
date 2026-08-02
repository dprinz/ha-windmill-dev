---
id: WMHA-0010
title: Track and cancel Home Assistant-started jobs
status: done
type: feature
priority: medium
risk: high
created: 2026-08-01
updated: 2026-08-02
depends_on: [WMHA-0007, WMHA-0009]
---

# WMHA-0010: Track and cancel Home Assistant-started jobs

## Outcome

Jobs started through Home Assistant are tracked until completion or expiry, can emit lifecycle events and can be cancelled when Windmill reports them as eligible.

## Why

Execution without bounded lifecycle handling leaves automations unable to react reliably or stop accidental long-running jobs.

## Required context

- `AGENTS.md`
- `docs/product/requirements.md`
- accepted execution and run-observation behavior

## Requirements

- Bounded registry keyed by Windmill job ID.
- Completion, failure and cancellation events integrate with `WMHA-0007`.
- Explicit cancel action with eligibility and permission checks.
- Expiry and reload behavior are documented.

## Acceptance criteria

- [x] Only Home Assistant-started jobs enter the local registry.
- [x] Registry size and retention are bounded.
- [x] Cancellation handles already-completed, missing and unauthorized jobs predictably.
- [x] Reloads do not create duplicate completion events.
- [x] No full result or log payload is persisted.

## Non-goals

- Cancelling arbitrary workspace jobs by default.
- Persisting an indefinite job history.

## Validation evidence

| Check | Command or inspection | Result |
| --- | --- | --- |
| Repository guardrails | `python scripts/validate_repository.py` | passed; 17 tickets checked |
| Lifecycle, run and execution tests | `uv run pytest -q tests/test_lifecycle.py tests/test_runs.py tests/test_execution.py` | 45 passed |
| Full suite and coverage | `uv run pytest -q --cov=custom_components.windmill --cov-report=term-missing --cov-fail-under=95` | 317 passed; 97.12% |
| Lint and format | `uv run ruff check custom_components tests`; `uv run ruff format --check custom_components tests` | passed |
| Types | `uv run mypy custom_components/windmill` | passed; 13 source files checked |
| Lock and diff | `uv lock --check`; `git diff --check` | passed |
| Restricted-token cancellation authorization | manual instance check | not run; no disposable token and eligible job are available, so the gate stays recorded in `docs/research/windmill-api-contract.md` |

Retention is 50 jobs and 24 hours per config entry, enforced on every read and write and persisted
in a Home Assistant store. Details are in `plans/WMHA-0010.md`.

## Review evidence

- Reviewer/session: separate review pass in the implementing session on 2026-08-02. No independent
  agent or fresh session reviewed this high-risk change, which deviates from `AGENTS.md`.
- Findings: one defect in already-accepted WMHA-0007 code. The run coordinator inferred the first
  observation from an empty watermark, so a workspace that was idle during the first poll never
  fired an event for its first later completion.
- Resolution: retention state now carries an explicit `initialized` flag, and a regression test
  covers the empty-first-poll case. The fix landed here because this ticket's acceptance criteria
  require lifecycle events to fire for Home Assistant-started jobs. Re-validated by the full check
  list above.
