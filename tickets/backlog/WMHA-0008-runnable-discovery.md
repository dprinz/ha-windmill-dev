---
id: WMHA-0008
title: Discover and select runnable scripts and flows
status: backlog
type: feature
priority: high
risk: medium
created: 2026-08-01
updated: 2026-08-01
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

- [ ] No runnable is executable before explicit selection.
- [ ] Removed or inaccessible runnables produce a recoverable unavailable state.
- [ ] Selection remains stable across reload and pagination order changes.
- [ ] Unsupported argument schemas are identified before execution is enabled.
- [ ] Search and selection scale to large workspaces without loading unbounded results.

## Non-goals

- Editing or deploying scripts and flows.
- Creating actions or button entities.

## Validation evidence

| Check | Command or inspection | Result |
| --- | --- | --- |
| Repository guardrails | `python scripts/validate_repository.py` | not run |
| Discovery and options tests | project test command | not run |

## Review evidence

- Reviewer/session: not started
- Findings: not started
- Resolution: not started
