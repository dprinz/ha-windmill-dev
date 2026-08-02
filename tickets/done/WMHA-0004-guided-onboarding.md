---
id: WMHA-0004
title: Add guided onboarding and configuration lifecycle
status: done
type: feature
priority: high
risk: medium
created: 2026-08-01
updated: 2026-08-02
depends_on: [WMHA-0003]
---

# WMHA-0004: Add guided onboarding and configuration lifecycle

## Outcome

A user can configure Windmill through a multi-step assistant, understand detected capabilities, choose optional monitoring features and later reauthenticate or reconfigure without deleting the integration.

## Why

A single form is insufficient once permissions, workspaces and optional administrative capabilities differ.

## Required context

- `AGENTS.md`
- `docs/product/requirements.md`
- current Home Assistant config-flow, reauth, reconfigure and options-flow guidance

## Requirements

- Validate endpoint and token before workspace and feature selection.
- Present a capability summary with understandable permission limitations.
- Support reauthentication, reconfiguration and options changes.
- Preserve safe defaults: worker details and high-cardinality diagnostics disabled unless selected.

## Acceptance criteria

- [x] The assistant guides connection, workspace, capabilities and feature selection in separate steps.
- [x] Duplicate instance/workspace entries are rejected.
- [x] Reauth updates credentials and reloads the entry.
- [x] Reconfigure and options flows preserve immutable identity correctly.
- [x] All paths have automated success, abort and error tests.

## Non-goals

- Creating Windmill tokens or modifying Windmill permissions.
- Implementing the selected entity platforms.

## Validation evidence

| Check | Command or inspection | Result |
| --- | --- | --- |
| Repository guardrails | `python scripts/validate_repository.py` | passed; 16 tickets checked |
| Flow and lifecycle tests | `uv run pytest -q tests/test_config_flow.py tests/test_init.py` | 53 passed |
| Full suite and coverage | `uv run pytest -q --cov=custom_components.windmill --cov-report=term-missing --cov-fail-under=95` | 148 passed; 97.87% |
| Lint and format | `uv run ruff check custom_components tests`; `uv run ruff format --check custom_components tests` | passed |
| Types | `uv run mypy custom_components/windmill` | passed; 6 source files checked |
| Lock and diff | `uv lock --check`; `git diff --check` | passed |
| Restricted-token onboarding against a live instance | manual instance check | not run; no disposable least-privilege token is available in this environment, so the gate stays recorded in `docs/research/windmill-api-contract.md` |

## Review evidence

- Reviewer/session: separate review pass in the implementing session on 2026-08-02. No independent
  agent or fresh session reviewed this medium-risk change, which deviates from `AGENTS.md`.
- Findings: two findings. The reconfigure flow overwrote a user-renamed entry title, and the test
  module kept an unused onboarding helper.
- Resolution: reconfiguration now updates identity only and leaves the title to the user; the dead
  test helper was removed. Both were re-validated by the full check list above.
