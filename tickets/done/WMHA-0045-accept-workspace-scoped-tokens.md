---
id: WMHA-0045
title: Accept workspace-scoped tokens that cannot address instance endpoints
status: done
type: bug
priority: high
risk: medium
created: 2026-08-05
updated: 2026-08-05
depends_on: []
---

# WMHA-0045: Accept workspace-scoped tokens that cannot address instance endpoints

## Outcome

A user can complete the config flow with a Windmill Cloud token that is valid inside its
workspace but is rejected by instance-wide endpoints. The flow reaches workspace selection,
validates through `whoami`, and reports the instance-wide endpoints as unavailable
capabilities instead of failing the credential.

## Why

Reported by the repository owner on 2026-08-05 against a Windmill Cloud test account. The
config flow fails at the first step with `invalid_auth` — "Das Token ist ungültig." — for a
token created without *Limit token permissions*.

Live verification against `https://app.windmill.dev` (`EE v1.779.0`) on 2026-08-05 with a
throwaway token shows the token is valid and the classification is wrong:

| Endpoint | Status |
| --- | --- |
| `GET /api/version` | `200` `EE v1.779.0` |
| `GET /api/health/status?force=false` | `200` |
| `GET /api/w/{workspace}/users/whoami` | `200`, `is_admin: true` |
| `GET /api/w/{workspace}/jobs/list` | `200` |
| `GET /api/w/{workspace}/scripts/list` | `200` |
| `GET /api/w/{workspace}/flows/list` | `200` |
| `GET /api/workspaces/list` | **`401`** |
| `GET /api/users/whoami` | **`401`** |
| `GET /api/health/detailed` | **`401`** |
| `GET /api/workers/list` | **`401`** |

The token authenticates for every workspace-scoped route and fails with `401` — not `403` —
on every instance-scoped route. Two code paths turn that into a rejected credential:

1. `WindmillInstanceClient.async_list_workspaces` maps `401` to
   `WindmillAuthenticationError`. `WindmillConfigFlow._async_validate_instance` catches that
   type explicitly and returns `invalid_auth`, so the flow never reaches workspace
   selection. Its existing fallback to manual workspace entry covers
   `WindmillAuthorizationError` and is never reached.
2. `WindmillInstanceClient._probe` deliberately re-raises `WindmillAuthenticationError`.
   Because `/api/health/detailed` and `/api/workers/list` also answer `401`,
   `async_discover_capabilities` would fail the workspace step for the same reason even
   after fixing the first path.

`docs/research/windmill-api-contract.md` anticipated restricted tokens losing access to
these endpoints, but assumed a `403` scope denial. The observed status is `401`, so the
assumption that "`401` proves the credential is bad" does not hold for instance-scoped
routes. The same run confirms `403` still occurs where documented: a granular-scoped token
returns `403 Access denied. Required scope: users:read` on workspace `whoami`.

## Required context

- `AGENTS.md`
- `custom_components/windmill/api.py` (`async_list_workspaces`, `_raise_for_status`,
  `_probe`, `_probe_json_object`, `_probe_json_list`, `async_discover_capabilities`)
- `custom_components/windmill/config_flow.py` (`_async_validate_instance`, `_map_client_error`)
- `docs/research/windmill-api-contract.md`
- `tests/test_api.py`, `tests/test_capabilities.py`, `tests/test_config_flow.py`

## Requirements

- A `401` from an instance-scoped endpoint must not be classified as an invalid credential.
- Workspace-scoped endpoints must keep mapping `401` to `WindmillAuthenticationError`;
  `whoami` remains the canonical credential validation.
- Workspace listing that answers `401` must fall back to manual workspace entry.
- Instance-scoped capability probes that answer `401` must degrade to an unavailable
  capability, not abort discovery.
- No change to the token transport: header-only `Authorization: Bearer <token>`.

## Acceptance criteria

- [x] `async_list_workspaces` raises `WindmillAuthorizationError` on `401`.
- [x] `/api/health/detailed` and `/api/workers/list` probes yield `UNAUTHORIZED` on `401`
      instead of propagating an authentication failure.
- [x] Workspace-scoped `401` still raises `WindmillAuthenticationError`, proven by a test
      that keeps `whoami` strict.
- [x] A config-flow test drives `workspaces/list` `401` and asserts the flow advances to the
      workspace step with manual entry rather than showing `invalid_auth`.
- [x] `docs/research/windmill-api-contract.md` records the observed `401` behaviour with the
      verification date.

## Non-goals

- Changing the token transport or supporting query-parameter tokens.
- Reworking the capability lattice or the feature-selection step.
- Making instance-scoped features work for workspace-scoped tokens; they stay unavailable.
- Any change to the MCP endpoint surface.

## Constraints

- Do not weaken authentication handling for workspace-scoped routes.
- Never log, expose or persist the token; diagnostics and issues stay token-free.
- Keep the client transport free of Home Assistant dependencies.

## Assumptions and research needs

| Item | Classification | Validation |
| --- | --- | --- |
| Windmill Cloud answers `401` for workspace-scoped tokens on instance-scoped routes | verified fact | Live probe against `app.windmill.dev` `EE v1.779.0` on 2026-08-05 |
| `Authorization: Bearer <token>` is the correct and only required transport | verified fact | `extract_token` at `windmill-api-auth/src/auth.rs#L523-L528`, tag `v1.775.2` |
| A genuinely invalid token still surfaces as `invalid_auth` at the workspace step | assumption | Covered by a config-flow test in this ticket |

## Validation evidence

| Check | Command or inspection | Result |
| --- | --- | --- |
| Repository guardrails | `uv run python scripts/validate_repository.py` | passed — 45 tickets checked |
| Tests | `uv run pytest` | passed — 439 passed |
| Lint | `uv run ruff check custom_components/windmill tests docs` | passed |
| Lint (repository-wide) | `uv run ruff check .` | 4 pre-existing `E501` in `scripts/validate_repository.py`, untouched by this ticket; see follow-up |
| Types | `uv run mypy custom_components/windmill` | passed — 16 source files |
| Live reproduction | Probe table above against `app.windmill.dev` | passed 2026-08-05 |
| Live acceptance | Repository owner set up a Windmill Cloud entry on release 0.3.1; entry `cloud-workspace` reports `loaded`, `managed_cloud: true`, `EE v1.779.0`, and every enabled coordinator reports `last_update_success: true` | passed 2026-08-05 |

## Review evidence

- Reviewer/session: not yet obtained; this is medium-risk work and `AGENTS.md` asks for an
  independent review before done. Implemented and released on the repository owner's direct
  instruction on 2026-08-05 with the live reproduction above as the primary evidence.
- Findings: none recorded.
- Resolution: open. A follow-up review pass should start from the diff and this ticket.

## Residual risks and follow-up

- An invalid token is now reported one step later, at workspace selection, because no
  instance-scoped endpoint can validate a workspace-scoped token. Accepted trade-off.
- The `401` behaviour is verified against Windmill Cloud only. Self-hosted CE/EE may answer
  `403`; that path is unchanged and still maps to the same capability outcome.
- No independent review yet, recorded above.
- The live acceptance run does not prove the fallback path itself: the token configured in Home
  Assistant reaches the instance-wide endpoints (both optional probes returned `available`), so
  that setup may never have hit the `401` on workspace listing. The mapping is covered by unit
  tests and the live probe; an end-to-end Cloud setup with a token that cannot list workspaces is
  still missing.
- 4 pre-existing `E501` violations in `scripts/validate_repository.py` are out of scope here
  and need their own ticket.

## Blog notes

- A `401` is only evidence about the credential when the endpoint is in the credential's own
  scope. Windmill Cloud returns `401`, not `403`, when a workspace-bound token addresses an
  instance-wide route, which made a valid token look revoked.
