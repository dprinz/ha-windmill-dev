---
id: WMHA-0024
title: Define config-entry-only CONFIG_SCHEMA for hassfest
status: backlog
type: chore
priority: low
risk: low
created: 2026-08-02
updated: 2026-08-02
depends_on: []
---

# WMHA-0024: Define config-entry-only CONFIG_SCHEMA for hassfest

## Outcome

hassfest reports no `[CONFIG_SCHEMA]` warning for the Windmill integration.

## Why

Found during WMHA-0014: the integration implements `async_setup`
(`custom_components/windmill/__init__.py:76`) without defining `CONFIG_SCHEMA`,
so hassfest emits a warning. The warning does not fail CI, but a clean hassfest
result is a precondition for a future HACS default-store submission.

## Required context

- `AGENTS.md`
- `custom_components/windmill/__init__.py`

## Requirements

- Add `CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)` (the standard
  pattern for config-flow-only integrations) unless inspection shows YAML setup
  is intentionally supported.
- Keep the change covered by the existing config-entry lifecycle tests.

## Acceptance criteria

- [ ] hassfest run for `custom_components/windmill` reports no warnings.
- [ ] Existing test suite passes unchanged.

## Non-goals

- YAML configuration support.

## Constraints

- No behavior change for UI-configured entries.

## Assumptions and research needs

| Item | Classification | Validation |
| --- | --- | --- |
| `cv.config_entry_only_config_schema` is the intended helper | assumption | Home Assistant developer documentation |

## Validation evidence

Fill during implementation; do not pre-check.

| Check | Command or inspection | Result |
| --- | --- | --- |
| Repository guardrails | `python scripts/validate_repository.py` | not run |

## Review evidence

- Reviewer/session:
- Findings:
- Resolution:

## Residual risks and follow-up

- None recorded

## Blog notes

- None
