# Agent handoff after WMHA-0010

- Handoff date: 2026-08-02
- Repository state: `main` at `283be2e`, pushed to `origin/main`
- Next ticket: `WMHA-0011` (still in `tickets/backlog/`; not activated)
- Last completed ticket: `WMHA-0010`
- Supersedes: `docs/development/handoff-after-WMHA-0003.md`

## Start here

Read these files in order before changing anything:

1. `AGENTS.md`
2. `docs/context-map.md`
3. `tickets/backlog/WMHA-0011-update-entity.md`
4. `docs/product/requirements.md`
5. `docs/architecture/decisions/0001-capability-negotiation.md`
6. `docs/research/windmill-api-contract.md`
7. The directly affected source and test files named below

There is intentionally no active ticket. Activate WMHA-0011 according to `AGENTS.md` and create
`plans/WMHA-0011.md` before implementing.

## Completed since the previous handoff

| Ticket | Commit | Result |
| --- | --- | --- |
| WMHA-0004 | `bc422d6` | Guided onboarding, reauthentication, reconfiguration and options flow |
| WMHA-0005 | `ec0c167` | Instance health entities and System Health |
| WMHA-0006 | `d307db2` | Worker-group and opt-in worker-instance observability |
| WMHA-0007 | `7e2f8a5` | Bounded run observability with one event entity |
| WMHA-0008 | `e9b4117` | Explicit runnable discovery and selection |
| WMHA-0009 | `31ab879` | `windmill.run` action and opt-in runnable buttons |
| WMHA-0010 | `283be2e` | Bounded started-job registry and `windmill.cancel` action |

The full suite is 317 tests at 97.12% coverage. Ruff, formatting, mypy, `uv lock --check`,
`scripts/validate_repository.py` and `git diff --check` pass.

## Current code map

| Area | File | Contract to preserve |
| --- | --- | --- |
| Entry lifecycle | `custom_components/windmill/__init__.py` | Builds the client, refreshes capabilities, creates only the coordinators the options and capabilities allow, loads the started-job registry and forwards four platforms |
| Transport and models | `custom_components/windmill/api.py` | `WindmillInstanceClient` owns instance-scoped calls, `WindmillClient` adds workspace-scoped calls; every response is bounded and allowlisted |
| Coordinators and state | `custom_components/windmill/coordinator.py` | Capability, health, worker, run and runnable coordinators plus the run retention model and the started-job registry |
| Flows | `custom_components/windmill/config_flow.py` | Four onboarding steps, reauth, reconfigure, and an options menu with feature and runnable steps |
| Actions | `custom_components/windmill/services.py` | `windmill.run` and `windmill.cancel`, both gated on explicit selection or local tracking |
| Entities | `sensor.py`, `binary_sensor.py`, `event.py`, `button.py`, `entity.py` | One service device per entry, translation-key naming, no entity per job or worker process |
| Tests | `tests/test_*.py` | Every feature is exercised through Home Assistant public interfaces |

## Invariants that later tickets must not break

- Credentials stay in config-entry data and the `Authorization` header only.
- Every client parser is an allowlist; denylisted fields (arguments, results, logs, IPs, emails,
  last-job identifiers, custom tags, worker-group configuration) are discarded in the client.
- A missing optional permission disables exactly one feature; it never fails the config entry.
- `401` from any authenticated call raises `ConfigEntryAuthFailed` and starts reauthentication.
- Entity sets are decided at setup from options plus capabilities, so capability churn changes
  entity state and not the entity registry.
- Only explicitly selected runnables are executable, and only jobs Home Assistant started are
  cancellable.
- Addressing mode is explicit: a pinned selection is never silently executed as latest.
- Feature options: `instance_health` and `run_observation` default on; `detailed_health`,
  `worker_groups`, `worker_details`, `update_entity` and `runnable_buttons` default off.

## Open gates that later tickets own

- Restricted-token onboarding, detailed-health token variants, Cloud tenant health and worker
  behavior, hash and version execution enforcement, and cancellation authorization are all still
  untested against a live instance. They remain recorded in `docs/research/windmill-api-contract.md`.
- `update_visibility=available` still proves only the endpoint contract. WMHA-0011 must establish
  Cloud versus self-host deployment eligibility before exposing an update entity.
- Translations are English only; WMHA-0013 owns German and the user documentation. Capability status
  tokens in the onboarding capability step are not translated yet.
- WMHA-0017 is a new backlog ticket for run-observation scope selection, which needs the selection
  from WMHA-0008 and the registry from WMHA-0010.

## Process deviation to correct

`AGENTS.md` requires an independent review for medium- and high-risk work. WMHA-0004 through
WMHA-0010 were reviewed only by a separate review pass inside the implementing session, because the
session was not permitted to spawn a reviewing agent. Each ticket records this deviation in its
review evidence. A fresh session should re-review at least the high-risk tickets WMHA-0006,
WMHA-0007, WMHA-0009 and WMHA-0010 before the WMHA-0015 release gate.

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
