---
id: WMHA-0026
title: Verify least-privilege and Cloud behavior against live instances
status: done
type: quality
priority: medium
risk: medium
created: 2026-08-02
updated: 2026-08-02
depends_on: [WMHA-0015]
---

# WMHA-0026: Verify least-privilege and Cloud behavior against live instances

## Outcome

The remaining live evidence gaps carried into the v1 release are closed with documented live checks, or the release risks in `docs/product/supported-versions-and-limitations.md` are re-confirmed and restated.

## Why

WMHA-0015 proved the client end-to-end against a disposable CE `v1.775.2` instance, but only with a superadmin token and only self-hosted. The least-privilege token story (the documented default for users) and Cloud tenant behavior rest on pinned-source evidence and mocks, not on live observation.

## Required context

- `AGENTS.md`
- `docs/product/supported-versions-and-limitations.md` (section "Evidence gaps carried into the release")
- `docs/development/v1-traceability-matrix.md` (section "Outstanding live checks")
- `docs/research/windmill-api-contract.md` (implementation gates)

## Requirements

- Mint a restricted (granular-scoped) token on a disposable self-hosted instance and verify: onboarding/whoami, script and flow execution by path and by pinned hash/version, and cancellation authorization behave as the contract predicts.
- Verify detailed-health behavior for granular-scoped tokens against a live instance.
- Where a Cloud test tenant can be obtained, probe tenant behavior for instance-global health and workers without collecting tenant data.
- Observe run observation against a workspace with real job traffic (bounded; no payload retention).
- Update `docs/product/supported-versions-and-limitations.md` and `docs/research/windmill-api-contract.md` with the results.

## Acceptance criteria

- [x] Each of the four open live checks in the traceability matrix is either closed with dated live evidence or explicitly re-confirmed as unverifiable with the reason. (2026-08-02, see "Live check results")
- [x] The public limitations document reflects the outcome. (`docs/product/supported-versions-and-limitations.md`, 2026-08-02)
- [x] No production credential is used; every live check uses disposable instances/tokens. (throwaway workspace, DB password and tokens; full cleanup verified)

## Non-goals

- Changing client behavior in response to findings (new tickets for any defect found).
- Home Assistant end-to-end deployment tests.

## Constraints

- Never use credentials of a productive system; never commit tokens.
- Live checks must not mutate anything outside disposable workspaces.

## Live check results (2026-08-02)

Method: disposable local Windmill CE `v1.775.2` (image `ghcr.io/windmill-labs/windmill:1.775.2`,
pull explicitly approved), docker compose project `wmha0026` bound to `127.0.0.1:8000`,
throwaway database password and first-boot superadmin login, throwaway workspace `smoke`.
All probes ran through the integration's own `WindmillClient`/`WindmillInstanceClient` plus
documented raw HTTP for exact status codes. Tokens lived only in process memory; nothing was
written to the repository. Containers, volumes and the pulled image were removed afterwards
(verified: no `wmha0026` containers/volumes, no Windmill images left).

1. **Restricted-token onboarding/execution/cancellation — closed.** A granular-scoped token
   (`users:read`, `workspaces:read`, `jobs:read`, `jobs:write`, `jobs:run:scripts`,
   `jobs:run:flows`, `scripts:read`, `flows:read`) was minted through
   `POST /api/users/tokens/create` → `201` (ticket assumption validated). With it:
   `async_validate` (whoami) OK; `async_list_workspaces` → `['smoke']`; script run by path
   and by pinned hash → `201`, completed `success`; flow run by path and by pinned version
   → `201`, completed `success`; `async_cancel_job` → `200`, job observed `canceled`.
   Capability discovery mapped a deliberately missing `workers:read` scope to
   `unauthorized/permission_denied` — the five-state behavior works live.
2. **Detailed health with granular-scoped token — closed.** Raw
   `GET /api/health/detailed` → `400` ("Could not extract domain from route:
   /api/health/detailed") for the granular token, `200` for an unscoped token — the pinned
   scope-middleware prediction confirmed with the precise status code. The client maps the
   `400` to `unsupported/unexpected_response` rather than `unauthorized`; tracked in new
   backlog ticket WMHA-0030.
3. **Cloud tenant — re-confirmed unverifiable.** No Cloud test tenant exists and none could
   be obtained without production credentials; provisioning one remains a human decision.
4. **Busy workspace — closed at synthetic-load level.** 9 concurrent jobs (6 success,
   2 failure, 1 canceled) were all observed through the bounded projection (`per_page=100`,
   one page, 22 unique jobs total — the 9 synthetic jobs plus 13 bootstrap/system and
   earlier-probe jobs in the same throwaway workspace): deduplicated by UUID, outcomes
   classified correctly (`success=6, failure=2, canceled=1`), and no payload fields (`args`,
   `result`, `logs`, `email`, `permissioned_as`) in the parsed model.

Minor transient observation, not a defect: the `jobs/list` capability probe failed once when
fired seconds after workspace creation (`unsupported/unexpected_response`), succeeded on
every repeat — same upstream propagation race class already recorded in WMHA-0015.

## Assumptions and research needs

| Item | Classification | Validation |
| --- | --- | --- |
| A restricted token can be minted through the API on a disposable instance | confirmed | live 2026-08-02: `POST /api/users/tokens/create` → `201` |
| A Cloud test tenant is obtainable | rejected | no tenant available; human decision, re-confirmed 2026-08-02 |

## Validation evidence

| Check | Command or inspection | Result |
| --- | --- | --- |
| Repository guardrails | `python scripts/validate_repository.py` | 2026-08-02: passed (30 tickets checked) |
| Whitespace | `git diff --check` | 2026-08-02: exit 0 |
| Tests | `uv run pytest -q` | 2026-08-02: 390 passed in 5.25s |
| Cleanup | `docker ps -a`; `docker volume ls`; `docker images` | 2026-08-02: no `wmha0026` containers/volumes, no Windmill images, `/tmp/wmha0026` deleted |

## Review evidence

- Reviewer/session: pending independent review
- Findings: pending independent review
- Resolution: pending independent review
