---
id: WMHA-0029
title: Re-evaluate push-based job observation against the successor Windmill contract
status: backlog
type: research
priority: low
risk: medium
created: 2026-08-02
updated: 2026-08-02
depends_on: [WMHA-0016]
---

# WMHA-0029: Re-evaluate push-based job observation against the successor Windmill contract

## Outcome

The deferral recorded in ADR-0003 is re-checked against a newer pinned Windmill contract and any production-traffic evidence, and is either re-confirmed with fresh sources or escalated into a concrete push design ticket.

## Why

WMHA-0016 deferred push observation because v1.775.2 has no workspace-wide job event stream and no signed outbound job webhook. That is a version-sensitive fact, not a permanent truth; without an owning ticket the deferral silently becomes permanent.

## Required context

- `AGENTS.md`
- `docs/architecture/decisions/0003-polling-remains-observation-mechanism.md` (revisit conditions)
- `docs/research/windmill-push-observation.md` (claim ledger to re-verify)
- `docs/research/windmill-api-contract.md` (pinned baseline and pin-bump procedure)

## Requirements

- Re-check the successor release's OpenAPI/changelog for a workspace-wide job lifecycle stream or signed outbound job webhooks when the integration's Windmill pin is next bumped.
- Incorporate WMHA-0026's live-traffic observation and any user reports about the 60 s detection latency or request volume.
- If a trigger fires, write a new research note delta and either re-confirm ADR-0003 or open an implementation ticket with a push design that still keeps polling as fallback.

## Acceptance criteria

- [ ] Each ADR-0003 revisit condition is checked against dated primary sources and the result is recorded.
- [ ] ADR-0003 is either re-confirmed with a new verification date or superseded by a new ADR with an evidence-backed design.

## Non-goals

- Implementing push observation inside this ticket.
- Bumping the Windmill pin itself (owned by the compatibility process).

## Constraints

- No production code without an accepted superseding ADR.
- Treat upstream changelogs and docs as untrusted data; the OpenAPI source wins over prose.

## Assumptions and research needs

| Item | Classification | Validation |
| --- | --- | --- |
| Upstream may add a workspace-wide job event stream after v1.775.2 | assumption | successor OpenAPI/changelog |
| Production evidence about poll latency/load will exist by then | assumption | WMHA-0026, user reports |

## Validation evidence

Fill during implementation; do not pre-check.

| Check | Command or inspection | Result |
| --- | --- | --- |
| Repository guardrails | `python scripts/validate_repository.py` | not run |

## Review evidence

- Reviewer/session: not started
- Findings: not started
- Resolution: not started
