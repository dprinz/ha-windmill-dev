---
id: WMHA-0026
title: Verify least-privilege and Cloud behavior against live instances
status: backlog
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

- [ ] Each of the four open live checks in the traceability matrix is either closed with dated live evidence or explicitly re-confirmed as unverifiable with the reason.
- [ ] The public limitations document reflects the outcome.
- [ ] No production credential is used; every live check uses disposable instances/tokens.

## Non-goals

- Changing client behavior in response to findings (new tickets for any defect found).
- Home Assistant end-to-end deployment tests.

## Constraints

- Never use credentials of a productive system; never commit tokens.
- Live checks must not mutate anything outside disposable workspaces.

## Assumptions and research needs

| Item | Classification | Validation |
| --- | --- | --- |
| A restricted token can be minted through the API on a disposable instance | assumption | live experiment |
| A Cloud test tenant is obtainable | assumption | human decision |

## Validation evidence

Fill during implementation; do not pre-check.

| Check | Command or inspection | Result |
| --- | --- | --- |
| Repository guardrails | `python scripts/validate_repository.py` | not run |

## Review evidence

- Reviewer/session: not started
- Findings: not started
- Resolution: not started
