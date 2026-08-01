---
id: WMHA-0003
title: Build the async client runtime and capability model
status: done
type: architecture
priority: high
risk: high
created: 2026-08-01
updated: 2026-08-02
depends_on: [WMHA-0001, WMHA-0002]
---

# WMHA-0003: Build the async client runtime and capability model

## Outcome

The integration has one typed asynchronous client, one config-entry runtime object and an explicit capability matrix that later platforms can consume without reconstructing Windmill API behavior.

## Why

Health, workers, jobs, execution and updates differ by Windmill edition and token permissions. These differences need one tested boundary before entities are added.

## Required context

- `AGENTS.md`
- `docs/product/requirements.md`
- `docs/architecture/overview.md`
- accepted output of `WMHA-0001` and `WMHA-0002`

## Requirements

- Typed models and domain errors for verified endpoints.
- Central authentication, timeout, pagination and response validation.
- Capability detection for health, workers, runs, execution, cancellation and update visibility.
- Shared runtime data and coordinators without global mutable state.

## Acceptance criteria

- [x] Client behavior is independent of Home Assistant entities and fully mock-testable.
- [x] Missing optional permissions produce unsupported capabilities rather than setup failure.
- [x] Authentication and transport failures remain distinguishable.
- [x] Config-entry setup, unload and reload close resources correctly.
- [x] No user-facing entities are added.

## Non-goals

- Onboarding UI beyond the initial config flow.
- Entity platforms or runnable execution.

## Validation evidence

| Check | Command or inspection | Result |
| --- | --- | --- |
| Repository guardrails | `python scripts/validate_repository.py` | passed; 16 tickets checked |
| Client and runtime tests | `uv run pytest -q tests/test_api.py tests/test_capabilities.py tests/test_init.py tests/test_config_flow.py` | 113 passed |
| Full suite and coverage | `uv run pytest -q --cov=custom_components.windmill --cov-report=term-missing --cov-fail-under=95` | 113 passed; 97.30% |
| Lint and format | `uv run ruff check custom_components tests`; `uv run ruff format --check custom_components tests` | passed |
| Types | `uv run mypy custom_components` | passed; 6 source files checked |
| Lock and diff | `uv lock --check`; `git diff --check` | passed |

## Review evidence

- Reviewer/session: independent `/root/review_wmha_0003` review and focused re-review on 2026-08-02
- Findings: one blocker (single-read streaming limit), three major findings (read/write capability conflation, unowned sibling probes after early authentication failure and overclaimed instance evidence) and two minor findings (unvalidated timestamps and lifecycle-evidence precision)
- Resolution: responses are read through EOF with an aggregate hard limit; discovery and contextual write capabilities are separate; probe tasks are cancelled and awaited on every escaping failure; live evidence and future gates are explicit; timestamps are timezone-aware and validated; lifecycle claims match the public callback test. Re-review found no blocker, no major finding and confirmed all six findings closed.
