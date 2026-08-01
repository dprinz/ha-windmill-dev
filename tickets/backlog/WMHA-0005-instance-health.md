---
id: WMHA-0005
title: Expose general Windmill instance health
status: backlog
type: feature
priority: high
risk: medium
created: 2026-08-01
updated: 2026-08-01
depends_on: [WMHA-0003, WMHA-0004]
---

# WMHA-0005: Expose general Windmill instance health

## Outcome

Home Assistant exposes a stable overall Windmill health state and bounded supporting diagnostics, while remaining useful when detailed administrative health data is unavailable.

## Why

Users need one automation-friendly signal that distinguishes healthy, degraded, unhealthy and unknown operation.

## Required context

- `AGENTS.md`
- `docs/product/requirements.md`
- accepted capability model from `WMHA-0003`

## Requirements

- Enum status entity for overall health.
- Supporting database, alive-worker and queue-depth diagnostics when available.
- Home Assistant System Health registration with redacted connection metadata.
- Coordinator-based polling with availability and recovery behavior.

## Acceptance criteria

- [ ] Overall status mapping is documented and covered for every upstream state and error class.
- [ ] Optional details disappear or become unavailable without failing the integration.
- [ ] Entity states and attributes remain bounded and contain no sensitive payloads.
- [ ] System Health reports instance identity, version and reachability without credentials.
- [ ] Polling is shared and does not issue one request per entity.

## Non-goals

- Worker-group entities.
- Persistent repairs for transient outages.

## Validation evidence

| Check | Command or inspection | Result |
| --- | --- | --- |
| Repository guardrails | `python scripts/validate_repository.py` | not run |
| Health platform tests | project test command | not run |

## Review evidence

- Reviewer/session: not started
- Findings: not started
- Resolution: not started
