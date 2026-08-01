---
id: WMHA-0009
title: Run selected scripts and flows from Home Assistant
status: backlog
type: feature
priority: high
risk: high
created: 2026-08-01
updated: 2026-08-01
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

- [ ] Unselected runnables cannot be executed through the integration.
- [ ] Invalid arguments fail before a network request when schema validation is possible.
- [ ] Authentication, permission, missing-runnable and server failures are distinguishable.
- [ ] Action responses contain only bounded non-sensitive metadata.
- [ ] Parameterless buttons are opt-in and do not duplicate action functionality by default.

## Non-goals

- Waiting synchronously for arbitrary job completion.
- Rendering arbitrary Windmill result payloads in Home Assistant state.

## Validation evidence

| Check | Command or inspection | Result |
| --- | --- | --- |
| Repository guardrails | `python scripts/validate_repository.py` | not run |
| Action and button tests | project test command | not run |

## Review evidence

- Reviewer/session: not started
- Findings: not started
- Resolution: not started
