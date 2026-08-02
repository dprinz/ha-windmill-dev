---
id: WMHA-0013
title: Complete translations and user documentation
status: done
type: documentation
priority: medium
risk: low
created: 2026-08-01
updated: 2026-08-02
depends_on: [WMHA-0004, WMHA-0009, WMHA-0012]
---

# WMHA-0013: Complete translations and user documentation

## Outcome

The integration has complete English and German user-facing text plus documentation for installation, permissions, configuration, entities, actions, removal and troubleshooting.

## Why

A public integration is not usable when capability limitations, permissions and automation behavior are only visible in source code.

## Required context

- `AGENTS.md`
- `docs/product/requirements.md`
- completed user-facing feature tickets

## Requirements

- English and German translations for all flows, errors, entities, actions and repairs.
- Safe examples for execution and run events.
- Permission matrix for basic and administrative features.
- Worker entity lifecycle guidance from `WMHA-0021`: which workspace-side changes require reloading
  the integration, why a silent worker reports `0` instead of disappearing, and the ephemeral
  `worker_instance` risk recorded in `docs/architecture/decisions/0002-worker-entity-lifecycle.md`.
- Removal and credential-revocation guidance, including the note added by `WMHA-0020` that stores
  orphaned by add-and-remove cycles before that change are not cleaned retroactively.

## Acceptance criteria

- [x] Translation validation reports no missing or orphaned keys.
- [x] Documentation distinguishes Cloud, self-hosted and permission-dependent behavior.
- [x] Examples use placeholders and contain no private infrastructure details.
- [x] Troubleshooting covers authentication, TLS, unsupported versions, workers and rate limits.
- [x] Documentation matches the final action and entity names exactly.

## Non-goals

- Marketing copy or a long-form blog article.
- Translating Windmill itself.

## Validation evidence

| Check | Command or inspection | Result |
| --- | --- | --- |
| Repository guardrails | `python scripts/validate_repository.py` | passed (23 tickets checked); new translation check reports no missing or orphaned keys for `en.json` and `de.json` |
| Translation and docs checks | `python scripts/validate_repository.py` with one key removed from and one ghost key added to `de.json` (then reverted) | failed as required with `missing translation key: config.error.invalid_auth` and `orphaned translation key: entity.sensor.ghost.name` |
| Placeholder parity | script comparing `{...}` placeholders per key between `en.json` and `de.json` | no mismatches |
| Name accuracy | inspection of `services.yaml`, `services.py`, `sensor.py`, `binary_sensor.py`, `event.py`, `button.py`, `update.py`, `issues.py` against the README tables | action names `windmill.run`/`windmill.cancel`, all entity names and the three repair issues match |
| Full suite and coverage | `uv run pytest -q --cov=custom_components.windmill --cov-report=term-missing --cov-fail-under=95` | passed, 374 tests, 97.22% |
| Lint, format and types | `uv run ruff check custom_components tests`; `uv run ruff format --check custom_components tests`; `uv run mypy custom_components/windmill` | passed |
| Lock and whitespace | `uv lock --check`; `git diff --check` | passed |

## Review evidence

- Reviewer/session: none; `AGENTS.md` requires an independent review only for medium- or
  high-risk changes, and this ticket is low-risk.
- Findings: self-check of the README against the source of truth for every documented action,
  entity and repair name; the translation check was proven to fail on both error directions
  before being left in place.
- Resolution: no change required.
