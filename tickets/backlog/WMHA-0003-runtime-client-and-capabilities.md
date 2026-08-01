---
id: WMHA-0003
title: Build the async client runtime and capability model
status: backlog
type: architecture
priority: high
risk: high
created: 2026-08-01
updated: 2026-08-01
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

- [ ] Client behavior is independent of Home Assistant entities and fully mock-testable.
- [ ] Missing optional permissions produce unsupported capabilities rather than setup failure.
- [ ] Authentication and transport failures remain distinguishable.
- [ ] Config-entry setup, unload and reload close resources correctly.
- [ ] No user-facing entities are added.

## Non-goals

- Onboarding UI beyond the initial config flow.
- Entity platforms or runnable execution.

## Validation evidence

| Check | Command or inspection | Result |
| --- | --- | --- |
| Repository guardrails | `python scripts/validate_repository.py` | not run |
| Client and runtime tests | project test command | not run |

## Review evidence

- Reviewer/session: not started
- Findings: not started
- Resolution: not started
