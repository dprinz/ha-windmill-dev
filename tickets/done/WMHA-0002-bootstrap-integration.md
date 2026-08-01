---
id: WMHA-0002
title: Bootstrap the Home Assistant integration and config flow
status: done
type: feature
priority: high
risk: medium
created: 2026-08-01
updated: 2026-08-02
depends_on: [WMHA-0001]
---

# WMHA-0002: Bootstrap the Home Assistant integration and config flow

## Outcome

A user can install the custom integration, enter a Windmill base URL, workspace and token in Home Assistant's UI, and receive a correctly classified success, authentication error or connection error.

## Why

A validated config entry is the smallest production foundation for all later script, flow and job capabilities.

## Required context

- `AGENTS.md`
- `docs/product/vision.md`
- `docs/architecture/overview.md`
- accepted output of `WMHA-0001`
- current Home Assistant config-flow and testing documentation

## Requirements

- Home Assistant custom integration under `custom_components/windmill/`.
- Home Assistant-independent asynchronous Windmill API client boundary.
- UI config flow with unique-instance handling and no YAML requirement.
- Credentials stored only in config-entry data and excluded from logs/diagnostics.
- Automated tests for setup success and principal failure classes.

## Acceptance criteria

- [x] Manifest and package structure pass the selected Home Assistant validation tooling.
- [x] A config flow validates the connection using an endpoint established by `WMHA-0001`.
- [x] Invalid authentication, unreachable instance and unexpected server response are distinct user-facing failures.
- [x] Duplicate configuration is prevented using a stable non-secret identity.
- [x] Setup, unload and reload behavior are covered through Home Assistant public interfaces.
- [x] No script/flow execution or entities are included in this ticket.

## Non-goals

- Running scripts or flows.
- Discovering workspace contents.
- Job status entities or callbacks.
- Disabling TLS verification.

## Constraints

- Depends on an accepted API/authentication contract from `WMHA-0001`.
- Must preserve a path toward current Bronze quality requirements.

## Assumptions and research needs

| Item | Classification | Validation |
| --- | --- | --- |
| Suitable low-cost authentication validation endpoint exists | unresolved dependency | `WMHA-0001` |

## Validation evidence

| Check | Command or inspection | Result |
| --- | --- | --- |
| Locked environment | `UV_CACHE_DIR=.agent-state/uv-cache uv sync --group dev --python 3.14` and `uv lock --check` | Passed with Python 3.14.6, Home Assistant 2026.7.4 and the locked dependency set |
| Tests and coverage | `uv run pytest -q --cov=custom_components.windmill --cov-report=term-missing --cov-fail-under=95` | 72 passed; 98.46% branch coverage |
| Lint | `uv run ruff check custom_components tests` | Passed with Ruff 0.16.1 |
| Format | `uv run ruff format --check custom_components tests` | Passed; 9 files already formatted |
| Types | `uv run mypy custom_components/windmill` | Passed in strict mode; 5 source files checked |
| Manifest and translations | Home Assistant manifest-loader test plus `python3.14 -m json.tool` for all three JSON files | Passed |
| Repository guardrails | `python scripts/validate_repository.py` | Passed; 16 tickets checked before final state transition |
| Diff hygiene | `git diff --check` | Passed |

## Review evidence

- Reviewer/session: independent `/root/review_wmha_0002` session, initial review and focused re-review on 2026-08-02
- Findings: two major findings — percent-encoded deployment paths could disagree with aiohttp/yarl canonicalization, and `whoami` 404 was classified as an invalid workspace without first proving the base deployment
- Resolution: path segments are decoded, checked and canonically re-encoded; `/api/version` is validated without authorization before `whoami`; regression tests cover aliases, traversal, call order, headers and failure mapping. Focused re-review closed both findings with no new blocker or major finding.

## Residual risks and follow-up

- No automated or manual test contacted a real Windmill or Home Assistant instance. Restricted-token and reverse-proxy behavior remains for `WMHA-0003` capability work.
- Reauthentication remains intentionally deferred to `WMHA-0004`.
- `cloud_polling` is a conservative manifest classification for the external service and should be reassessed when a coordinator and concrete monitoring behavior are introduced.

## Blog notes

- Added `docs/blog/2026-08-02-canonical-urls-before-duplicate-detection.md` because independent review exposed a reusable URL-identity lesson.
