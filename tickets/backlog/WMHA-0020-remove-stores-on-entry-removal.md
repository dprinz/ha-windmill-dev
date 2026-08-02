---
id: WMHA-0020
title: Delete persisted stores when a config entry is removed
status: backlog
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

- [ ] After removing a config entry, loading either store returns no data.
- [ ] A reload or unload leaves both stores intact, and deduplication across reloads still holds.
- [ ] Removing an entry whose stores were never written completes without error.
- [ ] Removing one entry does not touch the stores of another configured entry.
- [ ] A regression test covers entry removal and fails against the current implementation.

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
| `Store.async_remove` is the supported deletion path and tolerates a missing file | assumption | Verify against the pinned Home Assistant version during implementation |

## Validation evidence

Fill during implementation; do not pre-check.

| Check | Command or inspection | Result |
| --- | --- | --- |
| Repository guardrails | `python scripts/validate_repository.py` | not run |
| Init, run and lifecycle tests | `uv run pytest -q tests/test_init.py tests/test_runs.py tests/test_lifecycle.py` | not run |
| Full suite and coverage | `uv run pytest -q --cov=custom_components.windmill --cov-report=term-missing --cov-fail-under=95` | not run |
| Lint, format and types | `uv run ruff check custom_components tests`; `uv run ruff format --check custom_components tests`; `uv run mypy custom_components/windmill` | not run |

## Review evidence

- Reviewer/session: not started
- Findings: not started
- Resolution: not started

## Residual risks and follow-up

- Stores orphaned by earlier add-and-remove cycles are not cleaned retroactively. Decide during
  implementation whether that is acceptable or needs a note in the user documentation of
  `WMHA-0013`.

## Blog notes

- None
