---
id: WMHA-0029
title: Re-evaluate push-based job observation against the successor Windmill contract
status: done
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

- [x] Each ADR-0003 revisit condition is checked against dated primary sources and the result is recorded.
  - Workspace-wide job stream / signed outbound job webhooks: **not present in v1.776.0** (sole successor of v1.775.2, published 2026-08-01). Raw v1.776.0 `openapi.yaml` grepped 2026-08-02: exactly 10 `text/event-stream` occurrences in the same 3 execution-scoped families (`run_and_stream` ×8, `batch_rerun_jobs` ×1, `getupdate_sse` ×1); path diff vs v1.775.2 adds only dbt endpoints, per-job polled `run_progress`/`dbt_graph`, `seed_full_diff`, `github_app_stale_webhooks`. `edit_webhook` unchanged (bare URL, no signature field); webhooks docs re-fetched 2026-08-02 still list no job events; v1.776.0 release notes read in full — nothing relevant.
  - HA authenticated inbound webhook primitive: **unchanged** — HA webhook docs re-fetched 2026-08-02, still unauthenticated beyond secret id, `local_only` gate.
  - Production evidence: **still absent** — WMHA-0026 remains backlog; recorded as evidence boundary.
  - Windmill Cloud tenant-safe push channel: **not found**.
  - Recorded in `docs/research/windmill-push-observation.md`, section "Successor check 2026-08-02 (WMHA-0029)"; sources added to `docs/research/source-register.md`.
- [x] ADR-0003 is either re-confirmed with a new verification date or superseded by a new ADR with an evidence-backed design.
  - **Re-confirmed 2026-08-02** (no trigger fired): re-confirmation note added to ADR-0003 ("Re-confirmations" section).

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
| Repository guardrails | `python scripts/validate_repository.py` | passed 2026-08-02 (29 tickets checked, exit 0) |
| Diff hygiene | `git diff --check` | passed 2026-08-02 (no output, exit 0) |
| Test suite | not applicable | skipped — no production code changed (docs/plans/ticket only) |

## Review evidence

- Reviewer/session: pending independent review
- Findings: pending independent review
- Resolution: pending independent review
