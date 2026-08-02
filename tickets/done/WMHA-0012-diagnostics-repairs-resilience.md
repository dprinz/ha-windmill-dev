---
id: WMHA-0012
title: Add diagnostics, repairs and resilient recovery
status: done
type: quality
priority: high
risk: high
created: 2026-08-01
updated: 2026-08-01
depends_on: [WMHA-0004, WMHA-0005, WMHA-0006, WMHA-0007, WMHA-0011]
---

# WMHA-0012: Add diagnostics, repairs and resilient recovery

## Outcome

Users can diagnose integration problems safely, recover from authentication and connection failures, and receive repairs only for persistent actionable conditions.

## Why

Operational integrations need more than entities: failures must be explainable without leaking credentials or producing permanent noise.

## Required context

- `AGENTS.md`
- `docs/product/requirements.md`
- current Home Assistant diagnostics, repairs and availability guidance

## Requirements

- Redacted downloadable diagnostics.
- Backoff, recovery and log-throttling behavior for coordinators.
- Repair issues for unsupported versions, enabled features lacking permissions and inconsistent worker versions where actionable.
- Reauth handoff for invalid credentials.

## Acceptance criteria

- [x] Diagnostics exclude tokens, credential-bearing URLs, inputs, results, logs and stack traces.
- [x] Transient outages do not create persistent repairs.
- [x] Persistent actionable issues are created, updated and removed predictably.
- [x] Authentication failures initiate reauth without deleting user options.
- [x] Repeated failures do not spam logs or API requests.

## Non-goals

- Automatically changing Windmill permissions or deployment configuration.
- Uploading diagnostics externally.

## Implementation summary

- `diagnostics.py` builds a redacted payload from an explicit allowlist of bounded fields. Nothing
  is produced by dumping an object, so a field added later cannot leak by accident. The token, the
  base URL, the workspace, the entry title and the unique ID are redacted.
- `issues.py` derives issues from two observations. An enabled feature whose capability is
  `unauthorized` produces `missing_permission`; `unsupported` produces `unsupported_capability`;
  `temporarily_unavailable` produces nothing, because an outage is not a repair. Worker version
  drift becomes an issue only after it has persisted for 30 minutes, so a rolling upgrade is silent.
  Every issue is deleted as soon as its condition clears, and on unload.
- `coordinator.WindmillCoordinator` is a new shared base for all six coordinators. Subclasses
  implement `_async_observe`; the base applies rate-limit backoff and restores the configured
  interval on the next success. Backoff is bounded by `MAX_RATE_LIMIT_BACKOFF_SECONDS`.
- Log throttling needed no new mechanism: Home Assistant's `DataUpdateCoordinator` logs the first
  refresh failure at error level and every following one at debug level. The ticket needed evidence,
  which is now a test.
- Reauth already existed; the missing part was proof that it preserves the user's options.

## Deliberate behavior change

The capability coordinator had no listener before this ticket, so it never refreshed after setup
despite its six-hour interval. The issue evaluator now listens to it, which activates that interval.
The cost is one fixed set of bounded read-only probes every six hours per entry; the benefit is that
a permission fixed in Windmill clears its repair without a reload. This matches ADR-0001, which
specified the interval. Pinned by `test_capabilities_are_re_probed_so_an_issue_can_clear_itself`.

## Validation evidence

| Check | Command or inspection | Result |
| --- | --- | --- |
| Repository guardrails | `python scripts/validate_repository.py` | passed (23 tickets checked) |
| Diagnostics and repair tests | `uv run pytest -q tests/test_diagnostics.py tests/test_issues.py` | passed, 10 tests |
| Full suite and coverage | `uv run pytest -q --cov=custom_components.windmill --cov-report=term-missing --cov-fail-under=95` | passed, 374 tests, 97.22%; `diagnostics.py` and `issues.py` at 100%, `__init__.py` at 100% |
| Lint, format and types | `uv run ruff check custom_components tests`; `uv run ruff format --check custom_components tests`; `uv run mypy custom_components/windmill` | passed |
| Lock and whitespace | `uv lock --check`; `git diff --check` | passed |

## Review evidence

- Reviewer/session: separate review pass inside the implementing session; the same deviation from
  the independent-reviewer rule as `WMHA-0018` to `WMHA-0021` applies. This ticket is high risk, so
  the deviation matters more here than for the earlier ones — an independent review of this diff is
  the strongest remaining recommendation.
- Findings: four were checked and resolved during implementation. The diagnostics key for the base
  URL had to be `base_url`, because `async_redact_data` redacts by key name and a key called `url`
  silently survived the first version of the redaction test. The worker-drift evaluation had to
  ignore a failed poll, because `coordinator.data` then holds the previous snapshot — the same shape
  as the defect fixed in `WMHA-0022`. `options.get(option)` had to become
  `options.get(option, FEATURE_DEFAULTS[option])`, otherwise a user who never opened the options
  flow would get no issue for a feature that is on by default. The capability-coordinator listener
  turned out to be a real behavior change and is recorded above rather than left implicit.
- Open finding, not resolved: backoff applies only to explicit rate limiting, not to generic
  failures. Home Assistant does not back off either, and a fixed 60-second poll during an outage is
  not spam, so the fixed interval is kept deliberately. If a future measurement disagrees, it needs
  its own ticket.

## Residual risks and follow-up

- German translations for the three new issue texts are missing; `WMHA-0013` owns them.
- Diagnostics require a loaded entry, which is Home Assistant's own constraint for the download.
  A user whose entry fails to set up cannot download diagnostics for that failure.
- The 30-minute worker-drift grace period is a judgement, not a measurement.

## Blog notes

- None. The interesting finding — that a diagnostics key named `url` is not redacted by a
  `base_url` redaction list — is already recorded in the review evidence above.
