---
id: WMHA-0006
title: Expose worker-group and worker observability
status: backlog
type: feature
priority: high
risk: high
created: 2026-08-01
updated: 2026-08-01
depends_on: [WMHA-0003, WMHA-0005]
---

# WMHA-0006: Expose worker-group and worker observability

## Outcome

Authorized users can monitor worker groups and optionally individual workers through stable, bounded Home Assistant entities without making administrative permissions mandatory.

## Why

Worker availability, queue pressure and version drift are central operational signals for self-hosted Windmill installations.

## Required context

- `AGENTS.md`
- `docs/product/requirements.md`
- verified worker and health contracts from `WMHA-0001`

## Requirements

- Stable group identity and health mapping.
- Alive-worker count, queue pressure and version consistency where available.
- Individual worker entities only with stable identifiers and explicit opt-in.
- Graceful behavior for Cloud, edition and permission differences.

## Acceptance criteria

- [ ] Worker groups expose stable entities without registry churn when workers restart.
- [ ] Individual worker monitoring is disabled by default.
- [ ] Missing superadmin or equivalent permissions disable only detailed monitoring.
- [ ] Version inconsistency and unavailable groups are represented predictably.
- [ ] High-cardinality attributes and raw worker payloads are excluded.

## Non-goals

- Restarting workers or changing group assignments.
- Reproducing the Windmill worker administration UI.

## Validation evidence

| Check | Command or inspection | Result |
| --- | --- | --- |
| Repository guardrails | `python scripts/validate_repository.py` | not run |
| Worker platform tests | project test command | not run |

## Review evidence

- Reviewer/session: not started
- Findings: not started
- Resolution: not started
