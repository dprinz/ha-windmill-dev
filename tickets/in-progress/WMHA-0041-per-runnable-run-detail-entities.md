---
id: WMHA-0041
title: Expose per-runnable run detail entities for selected jobs
status: in-progress
type: feature
priority: medium
risk: medium
created: 2026-08-04
updated: 2026-08-04
depends_on: [WMHA-0040]
---

# WMHA-0041: Expose per-runnable run detail entities for selected jobs

## Outcome

A user who explicitly selected scripts and flows can enable one additional feature and then see,
per selected runnable, when it last ran, how that run ended, how long it took and whether it is
running right now. Each selected runnable appears as its own Home Assistant device below the
workspace device, so a dashboard card can be built per job.

## Why

Run observation today is a workspace aggregate: four sensors answer "did anything fail" but never
"did *this* job run". Requested by the repository owner on 2026-08-04: automations and dashboards
need per-job facts, and the set of interesting jobs is exactly the explicit selection the user
already maintains.

Reusing the existing selection keeps the promise of `docs/architecture/overview.md` — explicit
exposure instead of a whole workspace — and avoids a second list that can drift from the first.

## Required context

- `AGENTS.md`
- `docs/architecture/decisions/0002-worker-entity-lifecycle.md`
- `docs/architecture/decisions/0003-polling-remains-observation-mechanism.md`
- the per-runnable history subsection produced by `WMHA-0040`
- `custom_components/windmill/coordinator.py` (`WindmillRunCoordinator`,
  `WindmillRunnableCoordinator`, `RunnableSelection`, `ENTRY_STORES`)
- `custom_components/windmill/api.py` (`WindmillJob`, `async_list_jobs`)
- `custom_components/windmill/config_flow.py` (features and runnables steps)
- `custom_components/windmill/entity.py`, `sensor.py`, `binary_sensor.py`, `const.py`
- `tests/test_runs.py`, `tests/test_runnables.py`, `tests/test_config_flow.py`

## Requirements

- Add one opt-in feature option, default off, that turns the detail entities on. It is offered in
  the onboarding features step and the options features step, and its default is suppressed when
  the `runs` capability is not available.
- The feature applies to the runnables already selected in the options `runnables` step. No second
  selection list. Changing the selection reloads the entry and rebuilds the entity set; the
  reconfigure step keeps owning connection identity only.
- Per selected runnable expose exactly four entities: last-run timestamp, last-run status as a
  bounded enum, last-run duration, and a binary sensor for "running now".
- The status enum has a fixed option list covering success, failure, canceled and the state before
  anything was observed. Do not invent states outside `JobState`.
- Acquire history in two tiers: an exact filtered read per selection on a slow interval, and an
  immediate update from the rows the existing run window already returns. A completion seen in the
  fast window must be reflected without waiting for the slow tier.
- The slow tier reads `jobs/list` with `script_path_exact` set to one selection's path and
  nothing else from the filter set that collapses the union (`WMHA-0040`). It issues at most one
  request per selection per refresh, is bounded by the existing selection cap, and inherits the
  rate-limit backoff of `WindmillCoordinator`.
- Persist the last known per-runnable result across restarts in a bounded per-entry store, one
  record per selection, records for removed selections dropped. Register the store in
  `ENTRY_STORES` so entry removal cannot leave it behind.
- Each selected runnable becomes a device identified by entry, kind and path, linked to the
  workspace device via `via_device`.
- An entity whose runnable is missing or unauthorized reports unavailable rather than a stale
  value; the resolution already produced by `WindmillRunnableCoordinator` is the source for that.
- Add German and English strings for the new option, entities and status options, and include the
  feature state in diagnostics without adding any job payload.

## Acceptance criteria

- [x] With the feature off, no per-runnable entity and no per-runnable device exists, and no
      additional Windmill request is issued. —
      `test_feature_off_creates_nothing_and_asks_windmill_for_nothing`
- [x] With the feature on and two runnables selected, exactly eight entities exist on two devices,
      each device linked to the workspace device. —
      `test_each_selected_runnable_becomes_its_own_device`
- [x] A completion that appears only in the slow filtered read sets last run, status and duration.
      — `test_exact_read_answers_last_run_status_and_duration`
- [x] A completion that appears in the fast window is reflected in the same refresh cycle, without
      double-counting when the slow tier later returns the same job. —
      `test_shared_window_updates_details_without_starving_the_exact_read` and
      `test_an_older_completion_never_moves_the_last_run_backwards`
- [x] The last known values survive a config-entry reload and a Home Assistant restart. —
      `test_last_known_values_survive_a_reload`
- [x] Deselecting a runnable removes its entities on reload and drops its stored record. —
      `test_deselecting_a_runnable_drops_its_entities_and_its_record`
- [x] A runnable that becomes missing or unauthorized makes its entities unavailable. —
      `test_a_missing_runnable_makes_its_entities_unavailable`
- [x] A rate-limited detail refresh stretches the interval and does not fail the entry. —
      `test_a_rate_limited_detail_refresh_slows_down_instead_of_failing`
- [x] No argument, result, log, error text, worker or user field reaches entity state, attributes,
      diagnostics or logs. — `test_detail_state_carries_no_windmill_payload` and
      `test_per_runnable_listing_sends_only_the_union_preserving_filter`
- [x] The new option appears in `strings.json`, `translations/en.json` and `translations/de.json`.
- [x] Tests cover the criteria above through the public config-entry interface.

## Non-goals

- Next-run visibility. That is `WMHA-0042`.
- Detail entities for runnables the user did not select, or for flow steps and child jobs.
- One entity per job execution, run history lists, success rates or failure counters.
- Exposing job arguments, results or logs in any form.
- Changing the existing aggregate run sensors or the run event entity.

## Constraints

- Entity existence follows configuration, never volatile Windmill state
  (`docs/architecture/decisions/0002-worker-entity-lifecycle.md`).
- `_feature_capabilities` in `config_flow.py` must gain the new key. `_feature_defaults` only
  survives a missing key today because `FEATURE_DEFAULTS[key] and supported[key]` short-circuits
  on a false default; a new option must not rely on that.
- The selection cap of 25 makes 100 entities the worst case. The feature stays default-off and the
  ticket must record the measured request cost of one slow refresh at the cap.
- No new runtime dependency.
- The transport keeps its response-size bound; a filtered read must not be allowed to grow it.

## Assumptions and research needs

| Item | Classification | Validation |
| --- | --- | --- |
| An exact-path filtered read exists and is bounded | **verified 2026-08-04** | `WMHA-0040`: `jobs/list?script_path_exact={path}` keeps the union and carries `completed_at`; `jobs/completed/list` does not |
| The filtered read addresses flows the same way as scripts | **verified 2026-08-04** | `WMHA-0040`: the filter renders as `runnable_path IN (…)`, a unified column |
| A device per runnable is acceptable registry churn on selection change | decision | recorded with the human on 2026-08-04 |
| A Windmill deep link per runnable is safe as `configuration_url` | assumption | verify the URL shape, otherwise omit the link |

## Validation evidence

Fill during implementation; do not pre-check.

Run on 2026-08-04 with `uv run python -VV` reporting CPython 3.14.6.

| Check | Command or inspection | Result |
| --- | --- | --- |
| Repository guardrails | `python scripts/validate_repository.py` | pass — 43 tickets checked |
| Tests and coverage | `uv run pytest -q --cov=custom_components.windmill --cov-report=term-missing --cov-fail-under=95` | 424 passed, 98% total; every new module at 99-100% |
| Lint | `uv run ruff check custom_components tests` | pass |
| Format | `uv run ruff format --check custom_components tests` | pass — 32 files |
| Type check | `uv run mypy custom_components/windmill` | pass — 16 source files |
| Translation key parity | recursive key-set comparison of `strings.json` against both translations | identical |
| Request cost at the selection cap | inspection of `WindmillRunnableRunCoordinator._async_observe` | one request per selection per refresh, so 25 requests per five minutes at the cap of `MAX_SELECTED_RUNNABLES`; the fast tier adds none |
| CI on the pushed commit | GitHub Actions on `15deb3e` | 2026-08-04: `Tests, lint and types`, `Repository guardrails` and `Validate HACS and hassfest` all green |


## Review evidence

- Reviewer/session: not yet performed. This is medium-risk work — it adds a polling loop, a
  persistent store and a device model — so `AGENTS.md` asks for an independent review in a fresh
  session before this ticket moves to `done/`.
- Findings: pending review.
- Resolution: pending review.

## Deviations from the plan

- **The workspace device is now registered explicitly during setup.** `via_device` on the
  per-runnable devices pointed at a device that no entity had created yet whenever every
  workspace-level feature was off. Home Assistant logs this and states it will stop working,
  so `async_setup_entry` registers the workspace device itself.
- **Stale devices are pruned on setup.** A platform that stops adding an entity does not remove
  it; the registry keeps it as an orphan until a restart. Deselecting a runnable would have left
  a device of permanently unavailable entities behind, so `_async_prune_runnable_devices` drops
  the devices that no longer match the selection.
- **`_feature_defaults` was made explicit rather than only extended.** The plan called for adding
  the new key to `_feature_capabilities`. The lookup now also tolerates a feature with no single
  gating capability, because indexing the map directly was safe only by short-circuit accident.

## Residual risks and follow-up

- **No deep link per runnable.** A `configuration_url` on the per-runnable device would open the
  job in Windmill, but the UI route shape is unverified and was not guessed. A follow-up may add
  it after verifying the route the way `WMHA-0040` verified the API.
- **The exact read is a client-side maximum, not a promise.** `RUNNABLE_RUN_PAGE_SIZE` bounds
  only the completed half of the filtered union. A runnable with an extraordinary number of
  simultaneously queued jobs would still be bounded by `MAX_JOB_ROWS` and `MAX_RESPONSE_BYTES`,
  which fail closed rather than truncate.
- **`WMHA-0043`** records that pending scheduled jobs are still counted as queued work by the
  workspace aggregate.

## Blog notes

- A fast update path can starve the slow one it was meant to complement.
  `async_set_updated_data` reschedules a coordinator's next refresh, so folding a one-minute
  window into a five-minute coordinator through it would have pushed the exact read forever into
  the future — the tier that exists precisely for the jobs the window cannot see would never have
  run. Assigning `data` and calling `async_update_listeners()` notifies without touching the
  schedule. The bug would have been invisible in production: everything would have looked fresh,
  except for the rarely-run jobs that were the entire point.
