---
id: WMHA-0008
title: Discover and select runnable scripts and flows
status: done
type: feature
priority: high
risk: medium
created: 2026-08-01
updated: 2026-08-02
depends_on: [WMHA-0003, WMHA-0004]
---

# WMHA-0008: Discover and select runnable scripts and flows

## Outcome

Users can discover scripts and flows in the configured workspace, inspect safe metadata and explicitly choose which runnables Home Assistant may expose.

## Why

Automatic workspace-wide exposure would violate least privilege and create an unstable entity and action surface.

## Required context

- `AGENTS.md`
- `docs/product/requirements.md`
- verified runnable listing and schema contracts from `WMHA-0001`

## Requirements

- Paginated script and flow discovery.
- Explicit selection stored in config-entry options.
- Safe display of kind, path, summary and input schema metadata.
- Explicit latest-versus-pinned execution semantics.

## Acceptance criteria

- [x] No runnable is executable before explicit selection.
- [x] Removed or inaccessible runnables produce a recoverable unavailable state.
- [x] Selection remains stable across reload and pagination order changes.
- [x] Unsupported argument schemas are identified before execution is enabled.
- [x] Search and selection scale to large workspaces without loading unbounded results.

## Non-goals

- Editing or deploying scripts and flows.
- Creating actions or button entities.

## Validation evidence

| Check | Command or inspection | Result |
| --- | --- | --- |
| Repository guardrails | `python scripts/validate_repository.py` | passed; 17 tickets checked |
| Discovery, client and options tests | `uv run pytest -q tests/test_runnables.py tests/test_api.py tests/test_config_flow.py` | 197 passed |
| Full suite and coverage | `uv run pytest -q --cov=custom_components.windmill --cov-report=term-missing --cov-fail-under=95` | 274 passed; 97.56% |
| Lint and format | `uv run ruff check custom_components tests`; `uv run ruff format --check custom_components tests` | passed |
| Types | `uv run mypy custom_components/windmill` | passed; 11 source files checked |
| Lock and diff | `uv lock --check`; `git diff --check` | passed |
| Upstream listing and detail types | pinned `windmill-types/src/scripts.rs` and `flows.rs` at `v1.775.2`, read on 2026-08-02 | verified; listings carry no schema, so support is decided from the detail endpoints |
| Live discovery against a large workspace | manual instance check | not run; no workspace with a large runnable inventory is available |

Flow pinning is conditional. The verified flow types expose no version field, so a flow keeps
`latest` unless its detail response actually contains a numeric `version`. Script pinning uses the
hash, which both the listing and the detail response carry. The rationale is in `plans/WMHA-0008.md`.

## Review evidence

- Reviewer/session: separate review pass in the implementing session on 2026-08-02. No independent
  agent or fresh session reviewed this medium-risk change, which deviates from `AGENTS.md`.
- Findings: two findings. The options flow instantiated a full coordinator, which registers itself
  with the config entry, only to reuse its listing helper, and an abort string was added that no
  code path can produce.
- Resolution: discovery is now a plain async helper that takes the client, and the unused string was
  removed. Re-validated by the full check list above.
