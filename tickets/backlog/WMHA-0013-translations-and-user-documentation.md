---
id: WMHA-0013
title: Complete translations and user documentation
status: backlog
type: documentation
priority: medium
risk: low
created: 2026-08-01
updated: 2026-08-01
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
- Removal and credential-revocation guidance.

## Acceptance criteria

- [ ] Translation validation reports no missing or orphaned keys.
- [ ] Documentation distinguishes Cloud, self-hosted and permission-dependent behavior.
- [ ] Examples use placeholders and contain no private infrastructure details.
- [ ] Troubleshooting covers authentication, TLS, unsupported versions, workers and rate limits.
- [ ] Documentation matches the final action and entity names exactly.

## Non-goals

- Marketing copy or a long-form blog article.
- Translating Windmill itself.

## Validation evidence

| Check | Command or inspection | Result |
| --- | --- | --- |
| Repository guardrails | `python scripts/validate_repository.py` | not run |
| Translation and docs checks | project command | not run |

## Review evidence

- Reviewer/session: not started
- Findings: not started
- Resolution: not started
