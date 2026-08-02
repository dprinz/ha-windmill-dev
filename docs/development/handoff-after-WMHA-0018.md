# Agent handoff after WMHA-0018

- Handoff date: 2026-08-02
- Repository state: `main` after the WMHA-0018 commit
- Next ticket: `WMHA-0019` (in `tickets/backlog/`; activate it according to `AGENTS.md`)
- Last completed ticket: `WMHA-0018`
- Supersedes: `docs/development/handoff-after-WMHA-0011.md`

## Start here

Read these files in order before changing anything:

1. `AGENTS.md`
2. `docs/context-map.md`
3. `tickets/backlog/WMHA-0019-track-button-started-jobs.md`
4. `../done/WMHA-0009-runnable-execution.md` and `../done/WMHA-0010-job-lifecycle-control.md`
5. `custom_components/windmill/button.py`, `custom_components/windmill/services.py`
6. `tests/test_execution.py`, `tests/test_lifecycle.py`

There is intentionally no in-progress ticket. Move the selected ticket to `tickets/in-progress/`,
set its status in the same change, and create `plans/<ticket-id>.md` before implementing.

Everything the previous handoff recorded about architecture, invariants and open gates still
applies; read `docs/development/handoff-after-WMHA-0011.md` for that background. Only the deltas are
repeated here.

## Completed since the previous handoff

| Ticket | Result |
| --- | --- |
| WMHA-0018 | One observable Home Assistant event per observed completion; entry-owned, serialized forgetting of tracked jobs |

The full suite is 349 tests at 97.01% coverage. Ruff, formatting, mypy, `uv lock --check`,
`scripts/validate_repository.py` and `git diff --check` pass.

## What WMHA-0018 changed

- `custom_components/windmill/event.py` writes the entity state once per triggered completion. A
  triggered event is invisible until a state write, so a single write at the end of the loop
  published only the newest completion of a poll.
- Tracked completions of one poll are forgotten by one task created through
  `ConfigEntry.async_create_task`. An entry unload awaits that task instead of destroying it.
- `StartedJobRegistry.async_forget(*job_ids)` drops several jobs in one bounded write, and one
  `asyncio.Lock` serializes every registry mutation and store write, including `async_track` from
  the run action.

## New invariants

- One observed completion equals one state write on `event.<entry>_run`, in ascending
  `completed_at` order.
- Registry mutations are serialized; no two writes to the job store can interleave.
- Work started from an entity callback belongs to the config entry, never to `hass` directly.

## Open gates and follow-up

- `WMHA-0022` (new, backlog): a failed run poll republishes the completions of the previous
  successful poll, because `DataUpdateCoordinator` notifies listeners on failure and
  `coordinator.data` still holds the old snapshot. Reproduced during the WMHA-0018 review and
  deliberately not fixed there. It is the strongest remaining defect on the automation trigger path.
- The live-instance gates from the previous handoff are unchanged.
- Translations are still English only; WMHA-0013 owns German and the user documentation.

### Resulting order

`WMHA-0019` → `WMHA-0020` → `WMHA-0022` → `WMHA-0012`, with `WMHA-0021` whenever it fits.

`WMHA-0022` is placed before `WMHA-0012` for the same reason the review gave for the others: the
diagnostics ticket should not be built on a trigger path with a known duplication defect. Pulling
`WMHA-0022` forward ahead of `WMHA-0019` is defensible as well, since it affects every user with run
observation enabled, while `WMHA-0019` affects only users who enabled runnable buttons.

## Process deviation

`AGENTS.md` requires an independent review for medium- and high-risk work. WMHA-0018 was reviewed
only by a separate review pass inside the implementing session, because that session was not
permitted to spawn a reviewing agent. The ticket records this deviation and the one finding the pass
produced.

## Validation commands

```bash
uv run pytest -q --cov=custom_components.windmill --cov-report=term-missing --cov-fail-under=95
uv run ruff check custom_components tests
uv run ruff format --check custom_components tests
uv run mypy custom_components/windmill
uv lock --check
python scripts/validate_repository.py
git diff --check
```

## Git discipline

- One squashed commit per ticket, pushed to `origin/main` after the ticket is moved to `done`.
- Do not rewrite pushed history, publish releases or merge pull requests without explicit approval.
