---
id: WMHA-0005
title: Expose general Windmill instance health
status: done
type: feature
priority: high
risk: medium
created: 2026-08-01
updated: 2026-08-02
depends_on: [WMHA-0003, WMHA-0004]
---

# WMHA-0005: Expose general Windmill instance health

## Outcome

Home Assistant exposes a stable overall Windmill health state and bounded supporting diagnostics, while remaining useful when detailed administrative health data is unavailable.

## Why

Users need one automation-friendly signal that distinguishes healthy, degraded, unhealthy and unknown operation.

## Required context

- `AGENTS.md`
- `docs/product/requirements.md`
- accepted capability model from `WMHA-0003`

## Requirements

- Enum status entity for overall health.
- Supporting database, alive-worker and queue-depth diagnostics when available.
- Home Assistant System Health registration with redacted connection metadata.
- Coordinator-based polling with availability and recovery behavior.

## Acceptance criteria

- [x] Overall status mapping is documented and covered for every upstream state and error class.
- [x] Optional details disappear or become unavailable without failing the integration.
- [x] Entity states and attributes remain bounded and contain no sensitive payloads.
- [x] System Health reports instance identity, version and reachability without credentials.
- [x] Polling is shared and does not issue one request per entity.

## Non-goals

- Worker-group entities.
- Persistent repairs for transient outages.

## Validation evidence

| Check | Command or inspection | Result |
| --- | --- | --- |
| Repository guardrails | `python scripts/validate_repository.py` | passed; 16 tickets checked |
| Health and System Health tests | `uv run pytest -q tests/test_health.py tests/test_system_health.py tests/test_init.py` | 30 passed |
| Full suite and coverage | `uv run pytest -q --cov=custom_components.windmill --cov-report=term-missing --cov-fail-under=95` | 179 passed; 98.27% |
| Lint and format | `uv run ruff check custom_components tests`; `uv run ruff format --check custom_components tests` | passed |
| Types | `uv run mypy custom_components/windmill` | passed; 10 source files checked |
| Lock and diff | `uv lock --check`; `git diff --check` | passed |
| Detailed health with granular or administrative tokens, and Cloud tenant health | manual instance check | not run; no disposable token or Cloud tenant is available, so the gate stays recorded in `docs/research/windmill-api-contract.md` |

The status mapping, including the unreadable case that Home Assistant renders as `unavailable`
rather than a synthetic enum option, is documented in `plans/WMHA-0005.md`.

## Review evidence

- Reviewer/session: separate review pass in the implementing session on 2026-08-02. No independent
  agent or fresh session reviewed this medium-risk change, which deviates from `AGENTS.md`.
- Findings: one finding. The capability probe still used the discard-only detailed-health
  validator, so the probe and the entity path could drift apart.
- Resolution: both paths now use the same bounded parser, and the stale test fixture was replaced
  with a realistic detailed-health body. Re-validated by the full check list above.
