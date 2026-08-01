---
id: WMHA-0012
title: Add diagnostics, repairs and resilient recovery
status: backlog
type: quality
priority: high
risk: high
created: 2026-08-01
updated: 2026-08-01
depends_on: [WMHA-0004, WMHA-0005, WMHA-0006, WMHA-0007, WMHA-0011]
---

# WMHA-0012: Add diagnostics, repairs and resilient recovery

## Outcome

Users can diagnose integration problems safely, recover from authentication and connection failures, and receive repairs only for persistent actionable conditions.

## Why

Operational integrations need more than entities: failures must be explainable without leaking credentials or producing permanent noise.

## Required context

- `AGENTS.md`
- `docs/product/requirements.md`
- current Home Assistant diagnostics, repairs and availability guidance

## Requirements

- Redacted downloadable diagnostics.
- Backoff, recovery and log-throttling behavior for coordinators.
- Repair issues for unsupported versions, enabled features lacking permissions and inconsistent worker versions where actionable.
- Reauth handoff for invalid credentials.

## Acceptance criteria

- [ ] Diagnostics exclude tokens, credential-bearing URLs, inputs, results, logs and stack traces.
- [ ] Transient outages do not create persistent repairs.
- [ ] Persistent actionable issues are created, updated and removed predictably.
- [ ] Authentication failures initiate reauth without deleting user options.
- [ ] Repeated failures do not spam logs or API requests.

## Non-goals

- Automatically changing Windmill permissions or deployment configuration.
- Uploading diagnostics externally.

## Validation evidence

| Check | Command or inspection | Result |
| --- | --- | --- |
| Repository guardrails | `python scripts/validate_repository.py` | not run |
| Diagnostics and repair tests | project test command | not run |

## Review evidence

- Reviewer/session: not started
- Findings: not started
- Resolution: not started
