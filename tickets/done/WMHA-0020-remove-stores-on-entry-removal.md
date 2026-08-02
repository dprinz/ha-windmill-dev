---
id: WMHA-0020
title: Delete persisted stores when a config entry is removed
status: done
type: quality
priority: medium
risk: low
created: 2026-08-02
updated: 2026-08-02
depends_on: [WMHA-0007, WMHA-0010]
---

# WMHA-0020: Delete persisted stores when a config entry is removed

## Outcome

Removing a Windmill config entry removes the data that entry persisted. No run-observation state and
no started-job registry survive on disk after the integration is deleted.

## Why

Both retention models write per-entry stores that nothing ever deletes. A user who removes the
integration reasonably expects its stored data to be gone; today the identifiers, runnable paths and
timestamps stay in `.storage` indefinitely. Repeated add-and-remove cycles also accumulate orphaned
files that no code will ever read again.

This is the cheapest of the review findings to fix and the one with the clearest user expectation
behind it.

## Context

Found by the independent review of `WMHA-0006`, `WMHA-0007`, `WMHA-0009` and `WMHA-0010` on
2026-08-02.

`custom_components/windmill/__init__.py` defines `async_setup`, `async_setup_entry` and
`async_unload_entry`, but no `async_remove_entry`. Two stores are created per entry:

- `windmill.runs.<entry_id>` — watermark, the last 200 completed job identifiers, and the monotonic
  last-success and last-failure timestamps (`WMHA-0007`).
- `windmill.jobs.<entry_id>` — the bounded started-job registry with identifier, kind, path and
  start time (`WMHA-0010`).

Reproduced against the current implementation: after `hass.config_entries.async_remove(entry_id)`,
loading `Store(hass, 1, f"windmill.runs.{entry_id}")` still returned the full retention payload
including the `seen` job identifiers.

Home Assistant does not clean up `Store` files on entry removal; the integration must do it.

## Required context

- `AGENTS.md`
- `custom_components/windmill/__init__.py`
- `custom_components/windmill/coordinator.py` (`RunObservationState`, `StartedJobRegistry`)
- `docs/development/security-and-trust.md`
- `../done/WMHA-0007-run-observability.md`, `../done/WMHA-0010-job-lifecycle-control.md`

## Requirements

- Remove both per-entry stores when the config entry is removed.
- Keep removal resilient: a missing or unreadable store must not block entry removal.
- Do not remove stores on unload or reload, which must keep their state.
- Keep the store keys in one place so a future store cannot be forgotten here.

## Acceptance criteria

- [x] After removing a config entry, loading either store returns no data.
- [x] A reload or unload leaves both stores intact, and deduplication across reloads still holds.
- [x] Removing an entry whose stores were never written completes without error.
- [x] Removing one entry does not touch the stores of another configured entry.
- [x] A regression test covers entry removal and fails against the current implementation.

## Non-goals

- Migrating or versioning existing store payloads.
- Adding a user-facing action to clear history without removing the entry.
- Changing the retention bounds or the contents of either store.

## Constraints

- Store keys are derived from `entry_id` and must stay stable; this ticket must not rename them.
- Removal must not raise, or Home Assistant will leave the entry in place.

## Assumptions and research needs

| Item | Classification | Validation |
| --- | --- | --- |
| `Store.async_remove` is the supported deletion path and tolerates a missing file | confirmed | `homeassistant/helpers/storage.py` in the pinned version unlinks under `suppress(FileNotFoundError)` after invalidating the manager entry and cancelling both write listeners |

## Validation evidence

| Check | Command or inspection | Result |
| --- | --- | --- |
| Repository guardrails | `python scripts/validate_repository.py` | passed (22 tickets checked) |
| Init, run and lifecycle tests | `uv run pytest -q tests/test_init.py tests/test_runs.py tests/test_lifecycle.py` | passed |
| Regression check | Same files with `async_remove_entry` renamed so Home Assistant cannot find it | failed as required: `test_entry_removal_deletes_only_its_own_stores` |
| Full suite and coverage | `uv run pytest -q --cov=custom_components.windmill --cov-report=term-missing --cov-fail-under=95` | passed, 355 tests, 97.04%; `__init__.py` at 100% |
| Lint, format and types | `uv run ruff check custom_components tests`; `uv run ruff format --check custom_components tests`; `uv run mypy custom_components/windmill` | passed |
| Lock and whitespace | `uv lock --check`; `git diff --check` | passed |

## Review evidence

- Reviewer/session: separate review pass inside the implementing session; the same deviation from
  the independent-reviewer rule as `WMHA-0018` and `WMHA-0019` applies and is recorded here.
- Findings: three checks were made. Home Assistant really dispatches `async_remove_entry` from the
  component module — proven by the regression run, where renaming it made the removal test fail.
  Deduplication across reloads is untouched, since `test_duplicate_events_are_prevented_across_reloads`
  still passes with the store factories in place. `Store.async_remove` can still raise a non-missing
  `OSError`, which the failing-remove test now exercises, so removal completes even then.
- Resolution: no change required.

## Residual risks and follow-up

- Stores orphaned by add-and-remove cycles before this change are not cleaned retroactively. A
  retroactive sweep would have to guess which `windmill.*` store files belong to entries that no
  longer exist, so the decision is to document it instead; the requirement was added to `WMHA-0013`.

## Blog notes

- None
