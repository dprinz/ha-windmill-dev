---
id: WMHA-0011
title: Add read-only Windmill update visibility
status: backlog
type: feature
priority: medium
risk: medium
created: 2026-08-01
updated: 2026-08-01
depends_on: [WMHA-0003, WMHA-0005]
---

# WMHA-0011: Add read-only Windmill update visibility

## Outcome

Eligible self-hosted Windmill instances expose a Home Assistant update entity showing installed and latest version information without attempting deployment-specific upgrades.

## Why

Version drift is operationally relevant, but Home Assistant cannot safely abstract Docker, Kubernetes, Helm and other Windmill deployment methods into one install action.

## Required context

- `AGENTS.md`
- `docs/product/requirements.md`
- current Home Assistant update-entity guidance
- verified Windmill version and update-check contracts

## Requirements

- Detect installed backend version and latest-version or up-to-date status.
- Expose release-notes URL where a trustworthy source exists.
- Treat Windmill Cloud as managed and avoid a misleading update entity.
- Keep install support disabled unless a future deployment-specific contract is accepted.

## Acceptance criteria

- [ ] Update state maps correctly for current, outdated, unknown and unsupported instances.
- [ ] Cloud and unsupported editions do not expose a misleading entity.
- [ ] The entity has no install implementation in v1.
- [ ] Version parsing tolerates documented suffixes and development builds.
- [ ] Update checks are rate-limited and do not block normal health updates.

## Non-goals

- Pulling containers, changing Helm releases or restarting Windmill.
- Updating Home Assistant or this integration.

## Validation evidence

| Check | Command or inspection | Result |
| --- | --- | --- |
| Repository guardrails | `python scripts/validate_repository.py` | not run |
| Update-entity tests | project test command | not run |

## Review evidence

- Reviewer/session: not started
- Findings: not started
- Resolution: not started
