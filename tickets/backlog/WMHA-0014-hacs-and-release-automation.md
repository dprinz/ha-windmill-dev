---
id: WMHA-0014
title: Add HACS packaging and release automation
status: backlog
type: delivery
priority: medium
risk: medium
created: 2026-08-01
updated: 2026-08-01
depends_on: [WMHA-0013]
---

# WMHA-0014: Add HACS packaging and release automation

## Outcome

The integration can be installed through HACS and released reproducibly with validated artifacts, changelog notes and version metadata.

## Why

Manual ZIP publishing is error-prone and weakens trust in a public custom integration.

## Required context

- `AGENTS.md`
- `docs/product/requirements.md`
- current HACS and GitHub release requirements

## Requirements

- HACS metadata and repository validation.
- Versioning and changelog convention.
- CI release artifact generation from tags.
- No release publication without explicit human approval.

## Acceptance criteria

- [ ] HACS validation passes for the repository layout.
- [ ] Tagged builds produce the expected integration archive reproducibly.
- [ ] Manifest, release tag and artifact version agree.
- [ ] Release notes include breaking changes, permissions and migration notes.
- [ ] The workflow cannot publish from an untrusted pull-request context.

## Non-goals

- Submitting to Home Assistant Core.
- Automatically merging or publishing releases.

## Validation evidence

| Check | Command or inspection | Result |
| --- | --- | --- |
| Repository guardrails | `python scripts/validate_repository.py` | not run |
| HACS and artifact validation | project command | not run |

## Review evidence

- Reviewer/session: not started
- Findings: not started
- Resolution: not started
