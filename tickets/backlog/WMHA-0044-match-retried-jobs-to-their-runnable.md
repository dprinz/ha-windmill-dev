---
id: WMHA-0044
title: Match retried jobs to the runnable they belong to
status: backlog
type: bug
priority: low
risk: low
created: 2026-08-04
updated: 2026-08-04
depends_on: [WMHA-0041]
---

# WMHA-0044: Match retried jobs to the runnable they belong to

## Outcome

A selected script with a Windmill retry policy reports the outcome of the retry, not only of
the attempt that failed first. Whatever identity rule makes that true is verified against a
live instance and written down in `docs/research/windmill-api-contract.md`.

## Why

Everything that maps a job to a user selection compares `(job.job_kind, job.script_path)`
against the selection's `(kind, path)`: `WindmillRunnableRunCoordinator` for the per-runnable
detail entities, and `WindmillRunCoordinator._in_scope` for the `selected` run scope.

When a job with a retry policy fails, Windmill does not re-push it under its original kind. It
wraps it in a single-step flow: `retry_pending` pushes `JobPayload::SingleStepFlow` with
`path: job.runnable_path`, and that payload is materialized with
`job_kind: JobKind::SingleStepFlow`
([queue_jobs.rs L1871-L1890](https://github.com/windmill-labs/windmill/blob/v1.768.0/backend/windmill-queue/src/jobs.rs#L1871-L1890),
[L6015-L6025](https://github.com/windmill-labs/windmill/blob/v1.768.0/backend/windmill-queue/src/jobs.rs#L6015-L6025)).
The retry therefore arrives as `job_kind = "singlestepflow"` on the *script's* path, matches no
selection, and is dropped.

Observable effect: for a selected script with retries, `Last run`, `Last status` and
`Last duration` freeze on the first failed attempt while the successful retry is invisible, and
the `selected` run scope emits no event for it. Found while reviewing WMHA-0041 (2026-08-04);
the same comparison predates that ticket in `_in_scope`.

## Required context

- `AGENTS.md`
- `docs/research/windmill-api-contract.md` (jobs and run observation)
- `custom_components/windmill/coordinator.py` (`WindmillRunnableRunCoordinator._async_observe`,
  `async_apply_window`, `WindmillRunCoordinator._in_scope`)
- `custom_components/windmill/api.py` (`_parse_job`, `RunnableKind`)

## Requirements

- Verify against a live instance which `job_kind` values a selected script and a selected flow
  can legitimately produce. Do not guess a list from the OpenAPI enum: `singlestepflow`,
  `flowscript`, `flownode` and `aiagent` all exist, and only a live check shows which of them
  ever carry a user-visible runnable path as a top-level job.
- Decide whether the selection match should stay kind-based, become path-based with a bounded
  kind allowlist, or be dropped in favour of the path alone. Record the reason.
- Whatever is chosen must not let a *flow step* or a preview job land on a selection; the
  request filters `has_null_parent=true` and `is_flow_step=false` already exclude those.

## Acceptance criteria

- [ ] A retried job of a selected script updates that runnable's detail entities.
- [ ] The `selected` run scope covers the same jobs as the detail entities; no third rule.
- [ ] No job of another runnable, no flow step and no preview reaches a selection.
- [ ] The verified kind behaviour is documented in the research note with a date.

## Non-goals

- Reading or changing Windmill retry policies.
- Exposing retry counts or per-attempt history.

## Constraints

- Kind information may only be widened with live evidence; an allowlist guessed from the
  OpenAPI enum is exactly the kind of unverified claim `AGENTS.md` forbids.

## Assumptions and research needs

| Item | Classification | Validation |
| --- | --- | --- |
| A retry is pushed as `singlestepflow` on the original path | verified from pinned source 2026-08-04 | reproduce live with a failing script that has a retry policy |
| No other kind silently replaces a selected runnable's own kind | assumption | live check across script, flow and retried variants |

## Validation evidence

Fill during implementation; do not pre-check.

| Check | Command or inspection | Result |
| --- | --- | --- |
| Repository guardrails | `python scripts/validate_repository.py` | not run |

## Review evidence

- Reviewer/session:
- Findings:
- Resolution:

## Residual risks and follow-up

- Until this is fixed, the limitation is documented in
  `docs/product/supported-versions-and-limitations.md`.

## Blog notes

- None
