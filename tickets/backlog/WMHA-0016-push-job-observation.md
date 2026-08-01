---
id: WMHA-0016
title: Evaluate and add push-based job observation
status: backlog
type: research
priority: low
risk: high
created: 2026-08-01
updated: 2026-08-01
depends_on: [WMHA-0015]
---

# WMHA-0016: Evaluate and add push-based job observation

## Outcome

The project has measured evidence for whether SSE or webhook callbacks should supplement or replace polling, and implements the selected mechanism only when it improves reliability and cost without unsafe exposure.

## Why

Push updates may reduce latency and API traffic, but they introduce reconnect state, inbound reachability, authentication and lifecycle complexity.

## Required context

- `AGENTS.md`
- `docs/product/requirements.md`
- production observations from the stable polling implementation
- current Windmill SSE and webhook contracts

## Requirements

- Compare polling, SSE and webhook callbacks using measured API load, latency and failure recovery.
- Analyze Home Assistant restart, reconnect and network-boundary behavior.
- Require authenticated, replay-resistant callbacks if webhooks are selected.
- Preserve polling fallback unless evidence supports removal.

## Acceptance criteria

- [ ] A source-backed comparison records benefits, costs and unresolved risks.
- [ ] The selected design has an accepted ADR.
- [ ] Reconnect, duplicate, missed-event and restart scenarios are tested.
- [ ] No public inbound endpoint is required without explicit user choice and security documentation.
- [ ] The stable polling path remains available when push is unsupported.

## Non-goals

- Blocking the first stable release.
- Exposing arbitrary Windmill event payloads to Home Assistant.

## Validation evidence

| Check | Command or inspection | Result |
| --- | --- | --- |
| Repository guardrails | `python scripts/validate_repository.py` | not run |
| Push-observation tests | project test command | not run |

## Review evidence

- Reviewer/session: not started
- Findings: not started
- Resolution: not started
