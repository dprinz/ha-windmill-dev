---
id: WMHA-0017
title: Add run-observation scope selection
status: backlog
type: feature
priority: medium
risk: medium
created: 2026-08-02
updated: 2026-08-02
depends_on: [WMHA-0007, WMHA-0008, WMHA-0009]
---

# WMHA-0017: Add run-observation scope selection

## Outcome

A user can restrict run observation to all visible top-level jobs, to selected runnables or to jobs
that Home Assistant started, instead of always observing every visible top-level job.

## Why

`PR-006` requires configurable observation scope. WMHA-0007 implemented bounded observation of all
visible top-level jobs, because the two narrower scopes need data that did not exist yet: runnable
selection is introduced by WMHA-0008 and the Home Assistant-started job registry by WMHA-0009 and
WMHA-0010. Splitting the scope selector out keeps WMHA-0007 shippable without a half-wired option.

## Required context

- `AGENTS.md`
- `docs/product/requirements.md`
- the accepted output of `WMHA-0007`, `WMHA-0008` and `WMHA-0009`

## Requirements

- One option that selects between all visible top-level jobs, selected runnables and Home
  Assistant-started jobs.
- Filtering happens on bounded, already-parsed job metadata; no additional sensitive field is
  retained.
- Changing the scope must not replay historical jobs as new events.
- The retention model of WMHA-0007 keeps working across a scope change.

## Acceptance criteria

- [ ] The scope option is offered in onboarding and in the options flow with a safe default.
- [ ] Each scope value is covered by tests, including the transition between scopes.
- [ ] A scope change never fires events for jobs that completed before the change.
- [ ] Aggregate counters and last-run timestamps respect the selected scope.

## Non-goals

- Changing the polling model or the retention window of WMHA-0007.
- Per-job entities.

## Validation evidence

| Check | Command or inspection | Result |
| --- | --- | --- |
| Repository guardrails | `python scripts/validate_repository.py` | not run |
| Run-scope tests | project test command | not run |

## Review evidence

- Reviewer/session: not started
- Findings: not started
- Resolution: not started
