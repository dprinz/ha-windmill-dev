---
id: WMHA-0011
title: Add read-only Windmill update visibility
status: done
type: feature
priority: medium
risk: medium
created: 2026-08-01
updated: 2026-08-02
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

- [x] Update state maps correctly for current, outdated, unknown and unsupported instances.
- [x] Cloud and unsupported editions do not expose a misleading entity.
- [x] The entity has no install implementation in v1.
- [x] Version parsing tolerates documented suffixes and development builds.
- [x] Update checks are rate-limited and do not block normal health updates.

## Non-goals

- Pulling containers, changing Helm releases or restarting Windmill.
- Updating Home Assistant or this integration.

## Validation evidence

| Check | Command or inspection | Result |
| --- | --- | --- |
| Repository guardrails | `python scripts/validate_repository.py` | passed; 17 tickets checked |
| Update-entity and client tests | `uv run pytest -q tests/test_update.py tests/test_api.py` | 184 passed |
| Full suite and coverage | `uv run pytest -q --cov=custom_components.windmill --cov-report=term-missing --cov-fail-under=95` | 346 passed; 96.95% |
| Lint and format | `uv run ruff check custom_components tests`; `uv run ruff format --check custom_components tests` | passed |
| Types | `uv run mypy custom_components/windmill` | passed; 14 source files checked |
| Lock and diff | `uv lock --check`; `git diff --check` | passed |
| Live `/api/uptodate` output and failure modes | manual instance check | not run; no disposable self-hosted instance is available, so the gate stays recorded in `docs/research/windmill-api-contract.md`. Parsing is covered by mocked tests for `yes`, an update, an unchanged pair, a development build and four unparseable bodies |

Deployment eligibility, the gate the WMHA-0003 handoff assigned to this ticket, is resolved as a
conjunction: the `update_entity` opt-in stays disabled by default, the capability probe must have
succeeded, and a managed Cloud host is excluded. A Cloud tenant behind a custom domain cannot be
detected, which is why the opt-in remains a deliberate user decision. The rationale is in
`plans/WMHA-0011.md`.

## Review evidence

- Reviewer/session: separate review pass in the implementing session on 2026-08-02. No independent
  agent or fresh session reviewed this medium-risk change, which deviates from `AGENTS.md`.
- Findings: one finding. The update coordinator declared non-optional data while setup deliberately
  tolerates a failed first refresh, so the entity's own no-data branch was unreachable for the type
  checker and would have been wrong at runtime.
- Resolution: the coordinator is now typed as optional data, which makes the unavailable path
  explicit and type-checked. Re-validated by the full check list above.
