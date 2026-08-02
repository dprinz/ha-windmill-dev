# Agent handoff after WMHA-0012

- Handoff date: 2026-08-02
- Repository state: `main` after the WMHA-0012 commit, five commits ahead of the previous handoff
- Next ticket: `WMHA-0013` (in `tickets/backlog/`; activate it according to `AGENTS.md`)
- Last completed ticket: `WMHA-0012`
- Supersedes: `docs/development/handoff-after-WMHA-0018.md`

## Start here

Read these files in order before changing anything:

1. `AGENTS.md`
2. `docs/context-map.md`
3. `tickets/backlog/WMHA-0013-translations-and-user-documentation.md`
4. `custom_components/windmill/strings.json` and `custom_components/windmill/translations/en.json`
5. `docs/architecture/decisions/0002-worker-entity-lifecycle.md`

There is intentionally no in-progress ticket. Move the selected ticket to `tickets/in-progress/`,
set its status in the same change, and create `plans/<ticket-id>.md` before implementing.

The architecture background in `docs/development/handoff-after-WMHA-0011.md` still applies. Only the
deltas are repeated here.

## Completed in this session

| Ticket | Result |
| --- | --- |
| WMHA-0019 | One shared start-and-track path, so button-started jobs are tracked and cancellable |
| WMHA-0020 | `async_remove_entry` deletes both per-entry stores; store keys live in `ENTRY_STORES` |
| WMHA-0022 | The run event entity publishes only for a fresh observation |
| WMHA-0021 | ADR-0002 records the worker entity lifecycle trade-off |
| WMHA-0012 | Redacted diagnostics, actionable repair issues, rate-limit backoff |

The suite is 374 tests at 97.22% coverage. Ruff, formatting, mypy, `uv lock --check`,
`scripts/validate_repository.py` and `git diff --check` pass. Every commit is squashed per ticket;
nothing has been pushed.

## New invariants

- Every Home Assistant start path goes through `services.async_start_and_track_runnable`. A new
  start path that calls `async_start_runnable` directly is a defect.
- Every per-entry store is built through `coordinator.ENTRY_STORES`. A new store that is not in that
  tuple will survive entry removal.
- The run event entity publishes only for a snapshot it has not published and only after a
  successful poll.
- Every coordinator subclasses `WindmillCoordinator` and implements `_async_observe`, never
  `_async_update_data`. Overriding `_async_update_data` in a subclass silently disables backoff.
- Worker entity sets are fixed at setup; see ADR-0002 before changing anything about workers.
- Repair issues are derived, never asserted: `issues.async_evaluate_issues` re-derives all of them
  from the current observations on every capability or worker update.

## Deliberate behavior change in WMHA-0012

The capability coordinator had no listener and therefore never refreshed after setup. The issue
evaluator now listens to it, which activates the documented six-hour interval — one fixed set of
bounded read-only probes every six hours per entry. This is what ADR-0001 specified; it had simply
never taken effect.

## Open gates and follow-up

Backlog, in the order the evidence suggests:

- `WMHA-0013` — translations and user documentation. It now carries two handed-over requirements:
  the worker lifecycle guidance from `WMHA-0021` and the orphaned-store note from `WMHA-0020`.
  German is still entirely missing, including the three new `issues` texts added by `WMHA-0012`.
- `WMHA-0023` (new, found during `WMHA-0022`) — completions observed by the refresh during
  config-entry setup are never published, because the event entity is added afterwards. Every
  restart drops the completions that happened while Home Assistant was down. This is the strongest
  remaining defect on the automation trigger path.
- `WMHA-0017` — run-observation scope selection.
- `WMHA-0014` → `WMHA-0015` → `WMHA-0016` unchanged.

Placing `WMHA-0023` before `WMHA-0015` is recommended: the release quality gate should not certify a
trigger path that drops events across restarts.

## Process deviation

`AGENTS.md` requires an independent review for medium- and high-risk work. All five tickets were
reviewed only by a separate review pass inside the implementing session, because that session was
not permitted to spawn a reviewing agent. Each ticket records this and the findings its pass
produced. `WMHA-0012` is high risk and is the one where an independent review of the diff would be
most valuable before release.

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

- One squashed commit per ticket. The five commits of this session are local; pushing to
  `origin/main` needs the human's go-ahead.
- Do not rewrite pushed history, publish releases or merge pull requests without explicit approval.
