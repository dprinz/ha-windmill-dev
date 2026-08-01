# Agent handoff after WMHA-0003

- Handoff date: 2026-08-02
- Repository state: `main` at `b9f7df2`
- Next ticket: `WMHA-0004` (still in `tickets/backlog/`; not activated)
- Last completed ticket: `WMHA-0003`

## Start here

Read these files in order before changing anything:

1. `AGENTS.md`
2. `docs/context-map.md`
3. `tickets/backlog/WMHA-0004-guided-onboarding.md`
4. `docs/product/requirements.md`
5. `docs/architecture/overview.md`
6. `docs/architecture/decisions/0001-capability-negotiation.md`
7. `docs/research/windmill-api-contract.md`
8. The directly affected config-flow, runtime and test files named below

There is intentionally no active ticket. Confirm that WMHA-0004 satisfies the readiness criteria,
move it from `backlog` to `ready`, and then activate it according to `AGENTS.md`. Keep exactly one
implementation ticket in progress. Create `plans/WMHA-0004.md` before implementation because the
ticket spans multiple flow types and has non-trivial identity and credential risks.

Home Assistant flow behavior is version-sensitive. Verify current config-flow, reauthentication,
reconfigure and options-flow guidance from primary Home Assistant sources before committing to a
design, and record any durable external facts with their verification date.

## Completed foundation

Each completed ticket is represented by one local commit:

| Ticket | Commit | Result |
| --- | --- | --- |
| WMHA-0001 | `603dc3a` | Pinned and documented the Windmill API contract |
| WMHA-0002 | `dca7322` | Bootstrapped the integration and initial config flow |
| WMHA-0003 | `b9f7df2` | Added the typed async runtime client and capability matrix |

WMHA-0003 passed 113 tests at 97.30% coverage. Ruff, formatting, mypy, lock validation,
`scripts/validate_repository.py` and `git diff --check` passed. Its high-risk independent review
and focused re-review found no remaining blocker or major finding. The exact evidence is preserved
in `tickets/done/WMHA-0003-runtime-client-and-capabilities.md`.

At handoff creation, these three commits are local descendants of `origin/main`; nothing was
pushed or released.

## Current code map

| Area | File | Contract to preserve |
| --- | --- | --- |
| Entry lifecycle | `custom_components/windmill/__init__.py` | Builds one client, validates connection, performs first capability refresh and stores typed runtime data |
| Transport and models | `custom_components/windmill/api.py` | Owns URL construction, bearer headers, timeouts, response limits, parsing, errors and safe capability probes |
| Capability polling | `custom_components/windmill/coordinator.py` | One config-entry coordinator; authentication becomes `ConfigEntryAuthFailed`, other client failures become `UpdateFailed` |
| Runtime data | `custom_components/windmill/models.py` | Holds the client, validated connection and capability coordinator without global mutable state |
| Existing flow | `custom_components/windmill/config_flow.py` | Provides the WMHA-0002 single-step baseline and canonical duplicate identity |
| Flow tests | `tests/test_config_flow.py` | Covers setup, duplicate prevention and initial error mapping |
| Lifecycle tests | `tests/test_init.py` | Covers setup, unload, reload, runtime data and registered coordinator shutdown |
| Client tests | `tests/test_api.py` | Covers normalization, typed failures, bounded streaming and health parsing |
| Capability tests | `tests/test_capabilities.py` | Covers the five-state matrix, bounded probes, local failures and cancellation-safe fan-out |

## Architecture invariants

- The client remains independent of Home Assistant entities. Home Assistant-specific translation
  belongs in the adapter layer.
- Credentials stay in config-entry data and only enter an `Authorization: Bearer` header. Never
  place tokens in URLs, logs, entity state, diagnostics, fixtures or errors.
- Public version, coarse-health and update-contract requests do not send the token.
- All HTTP bodies use the central aggregate response limit. A stream must be read through EOF;
  the size argument of one asynchronous read is not an aggregate limit.
- Capability discovery owns every task it starts. An escaping failure cancels and awaits all
  sibling tasks before it is re-raised.
- Authenticated `401` means invalid authentication. Optional `403` and `404` remain local
  capability outcomes. Transport and server failures remain distinguishable and retryable.
- Script and flow discovery are read capabilities. Script execution, flow execution and
  cancellation remain `not_applicable/context_required` until a later explicit operation has a
  selected target. Never infer write permission from read access.
- `update_visibility=available` proves only the update endpoint contract, not whether a Cloud or
  managed deployment should receive an update entity.
- Setup and capability refresh use safe bounded GET requests only. They must not run or cancel a
  Windmill job.
- No entity platforms exist yet, so coordinator interval scheduling starts only after a later
  platform attaches listeners. The registered config-entry shutdown callback is already tested.

## WMHA-0004 implementation focus

The next ticket must replace the initial single form with a guided lifecycle covering connection,
workspace, capability explanation and opt-in feature selection. It also owns reauthentication,
reconfiguration and options changes. Preserve these boundaries:

- Validate endpoint and credentials before allowing workspace and feature selection.
- Continue to derive duplicate identity from the canonical base URL plus workspace.
- Keep immutable identity separate from adjustable options.
- Default high-cardinality or administrative monitoring features to disabled.
- Present partial capability support without treating an optional permission denial as total setup
  failure.
- Reauthentication may update credentials and reload the entry, but it must not silently change
  immutable instance/workspace identity.
- Do not create tokens, modify Windmill permissions or add entity platforms in WMHA-0004.

Cover every flow path through Home Assistant's public interfaces, including success, duplicate
abort, invalid authentication, unreachable server, malformed response, reauthentication,
reconfigure and options changes. Avoid assertions tied only to private helper implementation.

## Evidence still required by later tickets

- WMHA-0004 owns restricted-token onboarding and capability-presentation behavior. No disposable
  restricted token was available during WMHA-0003, so this was not live-tested.
- WMHA-0005 owns detailed-health behavior with granular/admin tokens and the relevant Cloud health
  variants.
- WMHA-0006 owns Cloud/self-host worker behavior.
- WMHA-0009 and WMHA-0010 own target-specific execution and cancellation authorization evidence.
- WMHA-0011 must establish deployment eligibility before exposing update behavior.

Do not obtain or reuse credentials from a running system merely to close one of these gates. Use a
disposable least-privilege token and an isolated target when live verification becomes necessary.
The prior live check was public/no-token and read-only; it changed no remote state.

## Validation commands

Run the narrowest WMHA-0004 tests first, then the complete repository checks:

```bash
uv run pytest -q tests/test_config_flow.py tests/test_init.py
uv run pytest -q --cov=custom_components.windmill --cov-report=term-missing --cov-fail-under=95
uv run ruff check custom_components tests
uv run ruff format --check custom_components tests
uv run mypy custom_components/windmill
uv lock --check
python scripts/validate_repository.py
git diff --check
```

Record actual results in the active ticket. WMHA-0004 is medium risk, so obtain an independent
review before moving it to `done`.

## Git and completion discipline

- Preserve unrelated user changes and inspect the worktree before editing.
- Keep the work limited to WMHA-0004 acceptance criteria; discovered follow-up work becomes a new
  backlog ticket unless it is required for acceptance.
- Keep exactly one final commit for WMHA-0004. If intermediate commits are useful, squash them
  before handoff.
- Do not push, release, merge or rewrite unrelated history without explicit user approval.
- Stop after the requested ticket boundary rather than silently activating the next ticket.
