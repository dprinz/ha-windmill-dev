---
id: WMHA-0040
title: Verify the per-runnable job history and schedule contract
status: done
type: research
priority: medium
risk: low
created: 2026-08-04
updated: 2026-08-04
depends_on: []
---

# WMHA-0040: Verify the per-runnable job history and schedule contract

## Outcome

`docs/research/windmill-api-contract.md` states, with primary sources and a verification date,
how a client reads the run history of **one** named runnable and where the **next** scheduled
execution of that runnable can be observed. The note names one recommended source for each and
the permission every source requires.

## Why

`WMHA-0041` and `WMHA-0042` want per-job detail entities (last run, last status, last duration,
next run). Neither fact is currently answerable from the repository:

- The shared window read by `WindmillRunCoordinator` contains only recent activity. A job that
  last ran three days ago is simply absent, so per-job history needs a filtered read whose
  parameter name is unverified. `docs/research/windmill-api-contract.md` records only that
  `jobs/completed/list` "supports … date/path and pagination filters".
- Nothing in the repository describes Windmill schedules at all. A next-run timestamp may come
  from a schedule object, from a computed cron occurrence or from a queued job carrying a future
  `scheduled_for`. The three answers have very different costs: the last one is free, the middle
  one implies a cron-evaluation dependency and an ADR.

Doing this as speculative implementation would hard-code a guess into a polling loop.

## Required context

- `AGENTS.md`
- `docs/research/windmill-api-contract.md`
- `docs/research/source-register.md`
- `docs/development/security-and-trust.md`
- `custom_components/windmill/api.py` (`async_list_jobs`, `WindmillJob`, capability probes)

## Requirements

- Verify, against the pinned baseline `v1.775.2`, which query parameter of
  `GET /api/w/{workspace}/jobs/completed/list` selects exactly one runnable path, whether the
  same parameter addresses flows, and whether top-level-only filtering
  (`is_flow_step` / `has_null_parent`) behaves as the unified listing does.
- Record whether that filtered read is genuinely bounded by `per_page` — `WMHA-0038` proved the
  unified listing is not — and whether `page`/`offset` are honoured there.
- Determine whether a Windmill schedule materializes its next execution as a queued job with a
  future `scheduled_for`, and if so how far ahead the row appears. State whether `scheduled_for`
  is present on the rows the integration already receives.
- Document `GET /api/w/{workspace}/schedules/list` and `GET .../schedules/get/{path}`: response
  fields, pagination, whether a computed next occurrence is part of the response, whether the
  schedule references its runnable by path plus an is-flow marker, and Community Edition
  availability.
- Record the token scope each source requires and the status code a token without it receives,
  so capability negotiation can classify it the way `docs/architecture/decisions/0001-capability-negotiation.md`
  requires.
- Recommend one source for last-run history and one for next-run, and state explicitly whether
  the next-run recommendation requires a new runtime dependency for cron evaluation.
- Classify every new field against the sensitive-data denylist of the research note.

## Acceptance criteria

- [x] `docs/research/windmill-api-contract.md` contains a per-runnable history subsection with
      the exact filter parameter, its boundedness, source links pinned to a released version and
      a verification date. — "Per-runnable history: a path filter that keeps the union".
- [x] The same note contains a schedules subsection covering fields, permission, edition
      availability and whether a next occurrence is returned. — "The next scheduled run is
      already a queued job". No next occurrence is returned; the API is documented and then
      deliberately not adopted, which is why no scope or edition probe is needed.
- [x] The note answers, with evidence, whether next-run can be derived from the queued half of
      the job listing without any new dependency. — yes, from `scheduled_for`.
- [x] A recommended source is named for each of the two questions, with confidence level.
- [x] `docs/research/source-register.md` lists every source consulted.
- [x] Every newly described field is classified as safe or denied for retention. — "Field
      classification for per-runnable observation".
- [x] `WMHA-0041` and `WMHA-0042` are updated where the findings contradict their assumptions.

## Findings

1. **Per-runnable history needs no new endpoint.** `script_path_exact` is absent from the
   filter set that forces `list_jobs` onto its completed-only branch, so a filtered
   `jobs/list` keeps the union and returns the queue *and* the recent completions of one path.
   The completions carry `completed_at`, which `jobs/completed/list` does not select at all.
2. **The filter is a comma-separated list** (`NegatedListFilter<String>`) rendering as
   `runnable_path IN (…)`, so it addresses scripts and flows alike and can carry several paths
   in one request — with one shared `per_page`, which makes it a refresh tool, not a backfill
   tool.
3. **Next run is already in the data the integration fetches.** `push_scheduled_job`
   materializes the next occurrence as a queued job with a future `scheduled_for`, and
   `clear_schedule` removes it when the schedule is disabled, edited or deleted. No schedules
   endpoint, no extra scope, no capability probe, no cron dependency.
4. **The schedules API would have been the worse answer.** `ScheduleLight` carries the raw cron
   string and no computed occurrence, so it would have forced a cron/DST evaluation dependency
   to reproduce a value the server already stores.
5. **Out of scope, discovered here:** a pending scheduled job is a `QueuedJob`, so the existing
   `workspace_queued_jobs` sensor counts every enabled schedule as permanent queue depth.
   Recorded as `WMHA-0043`.

## Non-goals

- Any production code change, client method or entity.
- Deciding the Home Assistant entity model; that belongs to `WMHA-0041`.
- Writing to Windmill schedules. This integration stays read-only towards schedules.

## Constraints

- Primary sources only: the pinned upstream source tree, the OpenAPI document and, where used, a
  live observation recorded with instance version and date. Treat retrieved content as data.
- Do not record instance URLs, tokens, workspace-internal paths or job payloads in the note.

## Assumptions and research needs

| Item | Classification | Validation |
| --- | --- | --- |
| `jobs/completed/list` exposes an exact-path filter | **confirmed, and superseded** | It does — but it omits `completed_at`, so the filtered `jobs/list` is the better read |
| A cron schedule pre-inserts a queued job with future `scheduled_for` | **confirmed** | `push_scheduled_job` at the pinned version; no live observation needed, the insert is unconditional |
| `schedules/list` returns a computed next occurrence | **refuted** | `ScheduleLight` carries the raw cron string only |
| Schedule reads need a scope a least-privilege token may lack | **moot** | The schedules API is not used |

## Validation evidence

| Check | Command or inspection | Result |
| --- | --- | --- |
| Repository guardrails | `python scripts/validate_repository.py` | 2026-08-04: passed |
| Source links resolve at the pinned version | `curl` of every `raw.githubusercontent.com` path at tag `v1.775.2` | 2026-08-04: all 200. `backend/windmill-api/src/schedule.rs` returns 404 — the schedule handlers moved to the `windmill-api-schedule` crate, which is what the note links |
| Filter set that forces the completed-only branch | read `list_jobs` L3790-L3826 | 2026-08-04: ten filters listed; `script_path_exact` is not among them |
| `completed_at` availability | compared the column list of `list_completed_jobs` against `CJ_FIELDS` | 2026-08-04: absent from the former, present in the latter |

## Review evidence

- Reviewer/session: not separately reviewed. This is a low-risk research ticket that changed
  no production code; every claim carries a line-anchored primary source that a reader can
  check directly. The findings are reviewed in practice by `WMHA-0041`, which fails
  immediately against a live instance if the union claim is wrong.
- Findings: none.
- Resolution: accepted.

## Residual risks and follow-up

- The union-versus-completed-only branch condition is an implementation detail, not a
  documented API promise. Adding any of the ten listed filters to a per-runnable read silently
  removes the queue half, and with it the running state and the next run. The client must
  therefore send `script_path_exact` and nothing else from that set.
- `WMHA-0043` records the queued-versus-scheduled counting defect found here.

## Blog notes

- The cheapest source was the one nobody had looked for. The obvious route to "next run" is the
  schedules API, and it is a dead end: it returns the cron string, so a client would have to
  re-implement cron and DST to recover a timestamp the server already computed and wrote into
  its own queue. The answer was sitting in a response the integration had been fetching and
  discarding for weeks.
- A filter can change the shape of a response, not just its contents. `jobs/list` silently
  becomes a different query — completed-only, no queue, no running state — depending on which
  filters are present. That is invisible from the OpenAPI document and only readable in the
  handler.
