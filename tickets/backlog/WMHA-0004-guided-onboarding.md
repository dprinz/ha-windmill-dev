---
id: WMHA-0004
title: Add guided onboarding and configuration lifecycle
status: backlog
type: feature
priority: high
risk: medium
created: 2026-08-01
updated: 2026-08-01
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

- [ ] The assistant guides connection, workspace, capabilities and feature selection in separate steps.
- [ ] Duplicate instance/workspace entries are rejected.
- [ ] Reauth updates credentials and reloads the entry.
- [ ] Reconfigure and options flows preserve immutable identity correctly.
- [ ] All paths have automated success, abort and error tests.

## Non-goals

- Creating Windmill tokens or modifying Windmill permissions.
- Implementing the selected entity platforms.

## Validation evidence

| Check | Command or inspection | Result |
| --- | --- | --- |
| Repository guardrails | `python scripts/validate_repository.py` | not run |
| Config-flow tests | project test command | not run |

## Review evidence

- Reviewer/session: not started
- Findings: not started
- Resolution: not started
