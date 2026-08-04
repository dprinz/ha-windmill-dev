---
id: WMHA-0039
title: Stop paging a jobs/list that ignores offset
status: backlog
type: quality
priority: low
risk: low
created: 2026-08-04
updated: 2026-08-04
depends_on: [WMHA-0038]
---

# WMHA-0039: Stop paging a jobs/list that ignores offset

## Outcome

The run coordinator stops issuing requests that cannot return new rows. Either the page walk
is replaced by a single bounded request, or it uses a cursor upstream actually honours.

## Why

`WindmillRunCoordinator._async_observe` walks up to `MAX_RUN_PAGES` pages by incrementing
`page`. Upstream `list_jobs` ignores the resulting offset: it logs
`"offset is not 0, but is ignored for list_jobs. Use created_before or completed_before
instead."` and builds the completed half with a hardcoded `offset 0`
([jobs.rs L2949-L3043](https://github.com/windmill-labs/windmill/blob/v1.768.0/backend/windmill-api/src/jobs.rs#L2949-L3043)).
Pages 2 and 3 therefore repeat page 1.

The consequence is bounded and not user-visible: UUID deduplication absorbs the repeats, and
after the first observation `_reached_watermark` ends the walk. It still costs up to two
useless requests per poll on a busy workspace and writes a warning into the user's Windmill
server log every time.

## Required context

- `AGENTS.md`
- `custom_components/windmill/coordinator.py` (`WindmillRunCoordinator`)
- `custom_components/windmill/api.py` (`async_list_jobs`)
- `docs/research/windmill-api-contract.md`
- `tests/test_runs.py`

## Requirements

- Decide between a single bounded request and a `created_before`/`completed_before` cursor.
  Note that setting `created_before` or `completed_before` makes upstream drop the queued
  half of the union entirely, which would remove the running/queued counts — a cursor walk
  probably needs a separate queue read.
- Keep the watermark, deduplication and event-emission behaviour unchanged.

## Acceptance criteria

- [ ] The run poll issues no request whose result upstream cannot vary.
- [ ] Watermark, deduplication and run-event behaviour stay covered and unchanged.
- [ ] The decision is recorded in the ticket, and in the research note if the contract
      understanding changes.

## Non-goals

- Changing the parsed job projection or the run-observation feature surface.
- Re-opening the `jobs/list` versus `jobs/queue/list` + `jobs/completed/list` source
  decision from WMHA-0038 unless the cursor design forces it.

## Constraints

- Do not widen the job projection or retain payload fields.

## Assumptions and research needs

| Item | Classification | Validation |
| --- | --- | --- |
| `created_before` suppresses the queued half of the union | verified from pinned source 2026-08-04 | re-read when the compatibility floor moves |

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

- None recorded

## Blog notes

- None
