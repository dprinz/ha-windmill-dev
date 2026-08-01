---
id: WMHA-0010
title: Track and cancel Home Assistant-started jobs
status: backlog
type: feature
priority: medium
risk: high
created: 2026-08-01
updated: 2026-08-01
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

- [ ] Only Home Assistant-started jobs enter the local registry.
- [ ] Registry size and retention are bounded.
- [ ] Cancellation handles already-completed, missing and unauthorized jobs predictably.
- [ ] Reloads do not create duplicate completion events.
- [ ] No full result or log payload is persisted.

## Non-goals

- Cancelling arbitrary workspace jobs by default.
- Persisting an indefinite job history.

## Validation evidence

| Check | Command or inspection | Result |
| --- | --- | --- |
| Repository guardrails | `python scripts/validate_repository.py` | not run |
| Lifecycle tests | project test command | not run |

## Review evidence

- Reviewer/session: not started
- Findings: not started
- Resolution: not started
