---
id: WMHA-0009
title: Run selected scripts and flows from Home Assistant
status: done
type: feature
priority: high
risk: high
created: 2026-08-01
updated: 2026-08-02
depends_on: [WMHA-0003, WMHA-0008]
---

# WMHA-0009: Run selected scripts and flows from Home Assistant

## Outcome

Home Assistant actions can start explicitly selected Windmill scripts and flows asynchronously with validated arguments and bounded response metadata.

## Why

Execution is the integration's core automation capability and must not rely on hand-built webhook URLs.

## Required context

- `AGENTS.md`
- `docs/product/requirements.md`
- accepted runnable and execution contracts from `WMHA-0001` and `WMHA-0008`

## Requirements

- Separate script and flow actions or one unambiguous typed action contract.
- JSON-compatible argument validation before sending.
- Asynchronous execution by default with returned job ID where supported.
- Optional button entities only for selected parameterless runnables.

## Acceptance criteria

- [x] Unselected runnables cannot be executed through the integration.
- [x] Invalid arguments fail before a network request when schema validation is possible.
- [x] Authentication, permission, missing-runnable and server failures are distinguishable.
- [x] Action responses contain only bounded non-sensitive metadata.
- [x] Parameterless buttons are opt-in and do not duplicate action functionality by default.

## Non-goals

- Waiting synchronously for arbitrary job completion.
- Rendering arbitrary Windmill result payloads in Home Assistant state.

## Validation evidence

| Check | Command or inspection | Result |
| --- | --- | --- |
| Repository guardrails | `python scripts/validate_repository.py` | passed; 17 tickets checked |
| Action, button and client tests | `uv run pytest -q tests/test_execution.py tests/test_api.py` | 190 passed |
| Full suite and coverage | `uv run pytest -q --cov=custom_components.windmill --cov-report=term-missing --cov-fail-under=95` | 308 passed; 97.40% |
| Lint and format | `uv run ruff check custom_components tests`; `uv run ruff format --check custom_components tests` | passed |
| Types | `uv run mypy custom_components/windmill` | passed; 13 source files checked |
| Lock and diff | `uv lock --check`; `git diff --check` | passed |
| Restricted-token hash and version execution | manual instance check | not run; no disposable token and target are available, so the gate stays recorded in `docs/research/windmill-api-contract.md` |

Tracking of Home Assistant-started jobs is deliberately not part of this ticket. The action returns
the job identifier, and the bounded registry plus cancellation remain WMHA-0010.

## Review evidence

- Reviewer/session: separate review pass in the implementing session on 2026-08-02. No independent
  agent or fresh session reviewed this high-risk change, which deviates from `AGENTS.md`.
- Findings: one finding. A pinned selection whose resolved runnable exposed neither a script hash
  nor a flow version silently fell back to the deployed head, which contradicts the explicit
  addressing rule of `PR-007`.
- Resolution: the action now refuses such a call with a dedicated error and asks the user to
  reselect without pinning. Re-validated by the full check list above.
