---
id: WMHA-0038
title: Bound job listing to the real shape of Windmill's jobs/list union
status: done
type: bug
priority: high
risk: medium
created: 2026-08-04
updated: 2026-08-04
depends_on: []
---

# WMHA-0038: Bound job listing to the real shape of Windmill's jobs/list union

## Outcome

Run observation works on a workspace that has jobs. Capability discovery reports `runs` as
`available` whenever `GET /api/w/{workspace}/jobs/list` is reachable and returns a JSON array,
and the run coordinator keeps refreshing when the response contains more rows than the
requested `per_page`, because upstream only applies `per_page` to the completed half of the
response.

## Why

On a live self-hosted CE `v1.768.0` instance with exactly one running job, capability
discovery reported `runs: unsupported / unexpected_response`, so the whole run-observation
feature disabled itself and raised a repair issue. The endpoint exists and the token is a
super-admin token; the probe rejected a well-formed answer.

Upstream `list_jobs` builds `queue UNION ALL completed`. Only the completed subquery receives
`per_page`; the queue subquery is built with `Pagination { per_page: None, page: None }`,
which `paginate_without_limits` turns into `MAX_PER_PAGE = 10000`, and the union has no outer
`LIMIT` ([jobs.rs L3010-L3043](https://github.com/windmill-labs/windmill/blob/v1.768.0/backend/windmill-api/src/jobs.rs#L3010-L3043),
[query.rs L252-L265](https://github.com/windmill-labs/windmill/blob/v1.768.0/backend/windmill-api-jobs/src/query.rs#L252-L265),
[utils.rs L297-L311](https://github.com/windmill-labs/windmill/blob/v1.768.0/backend/windmill-common/src/utils.rs#L297-L311)).
A request with `per_page=N` therefore returns *up to N completed rows plus every queued and
running top-level job*.

Both client-side bounds assume `per_page` is the row limit:

- `_probe_json_list` sends `per_page=1` and rejects any array longer than one row, so the
  probe fails as soon as one job is queued or running — the observed defect.
- `async_list_jobs` parses with `limit=page.per_page` (`RUN_PAGE_SIZE = 100`), so once a
  workspace has 100 completed jobs, any single concurrently running job makes every poll
  raise `WindmillProtocolError` and the coordinator fail. Fixing only the probe would enable
  the feature into a permanently failing coordinator, so this belongs to the same change.

## Required context

- `AGENTS.md`
- `docs/research/windmill-api-contract.md` (jobs and run observation)
- `custom_components/windmill/api.py` (`_probe_json_list`, `async_list_jobs`, `_parse_jobs`)
- `custom_components/windmill/coordinator.py` (`WindmillRunCoordinator._async_observe`)
- `tests/test_capabilities.py`, `tests/test_api.py`, `tests/test_runs.py`

## Requirements

- Derive the row bound for `jobs/list` from a documented client-side maximum instead of the
  requested page size, and explain the upstream union in a code comment.
- Keep every other list probe (`scripts/list`, `flows/list`, `workers/list`) on its current
  strict `per_page` bound; those endpoints honour it.
- Keep the run poll's requested page size low enough that a full page of completed rows plus
  a plausible queue stays inside `MAX_RESPONSE_BYTES` (64 KiB).
- Keep the page-walk stop condition meaningful now that a page can legitimately be longer
  than `per_page`.
- Record the upstream finding in `docs/research/windmill-api-contract.md` with source and
  verification date.

## Acceptance criteria

- [x] A `jobs/list` capability probe that returns more rows than the requested `per_page`
      yields `available / probe_succeeded`.
- [x] `async_list_jobs` parses a response with more rows than `per_page` and still fails
      closed above the documented client-side maximum.
- [x] The run page walk stops on the paginated (completed) half of the response, not on the
      total row count.
- [x] The upstream union behaviour is documented in the API contract research note with
      pinned source links and a verification date.
- [x] Tests, lint, format, types, lockfile and repository guardrails pass.

## Non-goals

- Switching run observation to `jobs/queue/list` and `jobs/completed/list`. Those endpoints
  paginate correctly but return full job rows including `args`; `jobs/list` deliberately
  nulls them (`null as args`), which is why it stays the source.
- Fixing the ignored `offset` of `jobs/list` (upstream logs it as a warning and hardcodes
  `offset 0` for the completed half). Tracked separately.
- Changing the run-observation feature, its scope options or its entities.

## Constraints

- Never widen the parsed job projection; `args`, `result`, `logs`, `email` and
  `permissioned_as` stay discarded.
- Keep the transport response cap (`MAX_RESPONSE_BYTES`) as the outer boundedness guarantee;
  the parse bound is a second guard, not a replacement.
- Do not silently truncate a job page: the union is not globally ordered, so dropping rows
  would drop completions and lose events.

## Assumptions and research needs

| Item | Classification | Validation |
| --- | --- | --- |
| The union shape is stable across the supported version range | assumption | re-read `list_jobs` when the compatibility floor moves; probe now tolerates both shapes |
| A serialized `UnifiedJob` row is well under 1 KiB with `include_args=false` | assumption | 38 mostly-null fields, no payload; re-check if the row grows |
| Workspaces observed by Home Assistant keep a small queue | assumption | a queue beyond the client bound fails the poll closed and is documented |

## Validation evidence

Fill during implementation; do not pre-check.

| Check | Command or inspection | Result |
| --- | --- | --- |
| Interpreter | `uv run python -VV` | Python 3.14.6 |
| Tests + coverage | `uv run pytest -q --cov=custom_components.windmill --cov-report=term-missing --cov-fail-under=95` | 406 passed, total coverage 97.30% (threshold 95%) |
| Lint | `uv run ruff check custom_components tests` | All checks passed |
| Format | `uv run ruff format --check custom_components tests` | 31 files already formatted |
| Types | `uv run mypy custom_components/windmill` | Success: no issues found in 16 source files |
| Lockfile | `uv lock --check` | Resolved 158 packages, lock consistent |
| Repository guardrails | `python scripts/validate_repository.py` | Repository validation passed (39 tickets checked) |
| Diff hygiene | `git diff --check` | no output (clean) |
| Release archive | `python scripts/build_release.py --tag v0.1.3 --output <tmp>` | version 0.1.3, sha256 `92ba6887…ccbfc` |

New tests, each failing without its fix:

- `tests/test_capabilities.py::test_run_probe_tolerates_the_unpaginated_queue_half` — the
  reported defect: a probe answer of three rows for `per_page=1` stays `available`.
- `tests/test_capabilities.py::test_runnable_probes_keep_the_strict_page_bound` — endpoints
  that honour `per_page` keep the strict bound; the relaxation is not global.
- `tests/test_capabilities.py` parametrization — a `jobs/list` answer above `MAX_JOB_ROWS`
  still reports `unsupported`/`unexpected_response`.
- `tests/test_api.py::test_job_listing_accepts_more_rows_than_the_page_size` — a page of
  five queued rows plus two completed rows parses with `per_page=2`.
- `tests/test_api.py::test_job_listing_rejects_invalid_models` — the oversize case now uses
  `MAX_JOB_ROWS + 1` rows instead of `per_page + 1`.
- `tests/test_runs.py::test_page_walk_ends_on_a_page_of_queued_jobs` — a page longer than
  `per_page` because of the queue does not promise another page.
- `tests/test_runs.py::test_page_walk_is_bounded` — rewritten: paging is driven by completed
  rows, and a job repeated across pages is counted once.

Not verified against the reporting live instance: the fix was derived from pinned upstream
source plus that instance's diagnostics (`runs: unsupported / unexpected_response`,
`sensor.*_laufende_jobs = 1`). Confirmation is the user's next setup after 0.1.3.

## Review evidence

- Reviewer/session: implementing session, self-review against ticket, diff and pinned
  upstream source. **No independent review** — the operating session was constrained to a
  single agent, so `AGENTS.md`'s independent-review expectation for medium-risk work was not
  met. Recorded as a residual risk rather than silently skipped.
- Findings: (a) scope initially limited to the probe would have enabled the feature into a
  permanently failing coordinator — polling was pulled into the same change; (b) reviewing
  the page walk surfaced a third defect, inflated running/queued counts from repeated pages
  (upstream ignores `offset`), fixed by deduplicating on job ID; (c) checked that the probe
  relaxation is per-call, so `scripts/list`, `flows/list` and `workers/list` keep the strict
  `per_page` bound; (d) checked that the parsed job projection and the payload denylist are
  untouched.
- Resolution: no open findings; the missing independent review stands as the one accepted
  deviation.

## Residual risks and follow-up

- A workspace with a very large queue still exceeds `MAX_RESPONSE_BYTES` and fails the poll
  closed; that is a graceful, retried failure, documented in
  `docs/product/supported-versions-and-limitations.md` rather than fixed here.
- No independent review (see above). A fresh session reviewing this diff would be cheap
  insurance before the next release.
- WMHA-0039 tracks the useless second and third page request that upstream's ignored offset
  causes; this ticket only stops it from corrupting the counts.

## Blog notes

- Candidate: a bounded client and a server that bounds only half of a union — why
  `per_page` is not a row count.
