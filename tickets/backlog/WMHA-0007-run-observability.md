---
id: WMHA-0007
title: Expose bounded run observability
status: backlog
type: feature
priority: high
risk: high
created: 2026-08-01
updated: 2026-08-01
depends_on: [WMHA-0003, WMHA-0005]
---

# WMHA-0007: Expose bounded run observability

## Outcome

Home Assistant exposes aggregate running, queued, successful and failed job information plus automation-friendly events for newly observed completions and failures.

## Why

Users need operational run visibility, but one entity per run would create registry churn, recorder growth and privacy risk.

## Required context

- `AGENTS.md`
- `docs/product/requirements.md`
- verified job-listing and filtering contract from `WMHA-0001`

## Requirements

- Aggregate counters and last-success/last-failure timestamps.
- Event entities for newly observed success, failure and cancellation.
- Configurable scope: all visible top-level jobs, selected runnables or Home Assistant-started jobs.
- Bounded polling, pagination and deduplication.

## Acceptance criteria

- [ ] No entity is created per job or run.
- [ ] Initial polling does not replay historical jobs as new events.
- [ ] Duplicate events are prevented across reloads within the documented retention model.
- [ ] Raw arguments, logs, stack traces and full results never enter state or diagnostics.
- [ ] Pagination and rate-limit behavior are tested.

## Non-goals

- Full Runs-page replication.
- Job cancellation or execution.

## Validation evidence

| Check | Command or inspection | Result |
| --- | --- | --- |
| Repository guardrails | `python scripts/validate_repository.py` | not run |
| Run-observation tests | project test command | not run |

## Review evidence

- Reviewer/session: not started
- Findings: not started
- Resolution: not started
