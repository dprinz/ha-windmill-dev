---
id: WMHA-0006
title: Expose worker-group and worker observability
status: done
type: feature
priority: high
risk: high
created: 2026-08-01
updated: 2026-08-02
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

- [x] Worker groups expose stable entities without registry churn when workers restart.
- [x] Individual worker monitoring is disabled by default.
- [x] Missing superadmin or equivalent permissions disable only detailed monitoring.
- [x] Version inconsistency and unavailable groups are represented predictably.
- [x] High-cardinality attributes and raw worker payloads are excluded.

## Non-goals

- Restarting workers or changing group assignments.
- Reproducing the Windmill worker administration UI.

## Validation evidence

| Check | Command or inspection | Result |
| --- | --- | --- |
| Repository guardrails | `python scripts/validate_repository.py` | passed; 16 tickets checked |
| Worker, client and flow tests | `uv run pytest -q tests/test_workers.py tests/test_api.py tests/test_config_flow.py` | 136 passed |
| Full suite and coverage | `uv run pytest -q --cov=custom_components.windmill --cov-report=term-missing --cov-fail-under=95` | 210 passed; 98.46% |
| Lint and format | `uv run ruff check custom_components tests`; `uv run ruff format --check custom_components tests` | passed |
| Types | `uv run mypy custom_components/windmill` | passed; 10 source files checked |
| Lock and diff | `uv lock --check`; `git diff --check` | passed |
| Upstream `WorkerPing` field list | pinned worker handler at `v1.775.2`, read on 2026-08-02 | verified; `ip`, both last-job fields and `custom_tags` are discarded in the client |
| Cloud tenant worker behavior | manual instance check | not run; no Cloud test tenant is available, so the gate stays recorded in `docs/research/windmill-api-contract.md` |

Queue pressure is deliberately not duplicated per tag. `/api/workers/queue_counts` and its running
variant are DevOps-gated and keyed by tag rather than by worker group, so WMHA-0005 remains the
source of bounded pending and running job counts. The rationale is recorded in `plans/WMHA-0006.md`.

## Review evidence

- Reviewer/session: separate review pass in the implementing session on 2026-08-02. No independent
  agent or fresh session reviewed this high-risk change, which deviates from `AGENTS.md`.
- Findings: two findings. A worker instance and a worker group with the same name produced two
  entities with an identical display name, and the snapshot carried a truncation flag that no
  consumer read.
- Resolution: per-instance entities are now named `Workers on {instance}`, and the unread flag was
  removed in favor of the existing debug message. Re-validated by the full check list above.
