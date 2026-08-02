---
id: WMHA-0028
title: Report effective feature defaults in diagnostics
status: done
type: quality
priority: low
risk: low
created: 2026-08-02
updated: 2026-08-02
depends_on: [WMHA-0012]
---

# WMHA-0028: Report effective feature defaults in diagnostics

## Outcome

Diagnostics report the effective feature flags, so an entry whose options flow was never
opened shows the real defaults instead of `false` everywhere.

## Context

Found by the independent WMHA-0012 diff review (2026-08-02).
`custom_components/windmill/diagnostics.py:50` uses `bool(entry.options.get(option))`
without the `FEATURE_DEFAULTS` fallback that `issues.py:80` and `__init__.py` already apply.
No secret is involved; the diagnostic information is simply wrong for the default case.

## Acceptance criteria

- [x] Diagnostics reflect `FEATURE_DEFAULTS` for options that were never stored.
- [x] A test covers the default case and the explicitly-disabled case.

## Non-goals

- Changing the diagnostics schema or adding new fields.

## Validation evidence

| Check | Command or inspection | Result |
| --- | --- | --- |
| Repository guardrails | `python scripts/validate_repository.py` | passed (28 tickets checked) |
| Full suite | `uv run pytest -q --cov=custom_components.windmill --cov-report=term-missing --cov-fail-under=95` | 390 passed, 97.28% coverage |
| Lint | `uv run ruff check custom_components tests` | passed |
| Format | `uv run ruff format --check custom_components tests` | 31 files already formatted |
| Types | `uv run mypy custom_components/windmill` | no issues in 16 source files |
| Lockfile | `uv lock --check` | passed |
| Whitespace | `git diff --check` | passed |
| Defect reproduction | Default-case test run against the pre-fix code (via `git stash`) | failed on the old code, passes on the fix |

## Review evidence

- Reviewer/session: not needed (low risk, per AGENTS.md)
- Findings: none
- Resolution: n/a
