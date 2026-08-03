---
id: WMHA-0037
title: Freeze time in the tracked job registry bound test
status: ready
type: bug
priority: medium
risk: low
created: 2026-08-03
updated: 2026-08-03
depends_on: []
---

# WMHA-0037: Freeze time in the tracked job registry bound test

## Outcome

`tests/test_lifecycle.py::test_registry_is_bounded_by_size_and_age` passes regardless of the
date on which it runs, and still verifies both bounds it claims to verify: the size cap
`MAX_TRACKED_JOBS` and the age cap `TRACKED_JOB_TTL_HOURS`.

## Why

Observed on 2026-08-03 while validating WMHA-0036, on unmodified `master`:

```
assert len(registry.tracked) == MAX_TRACKED_JOBS
E       assert 0 == 50
```

The test builds tracked jobs at fixed timestamps starting at `2026-08-02 10:00 UTC` and then
asserts the size cap. `StartedJobRegistry` prunes by `TRACKED_JOB_TTL_HOURS` against real
wall-clock time, so once the clock passes that TTL every fixture job is expired and the
registry is empty. The production pruning is correct; the test is time-dependent and rots.

This was a passing test when it was written, which makes it worse than a failing one: it now
masks the size bound it was supposed to guard, and it will keep failing on every future run
until the timestamps are decoupled from the real clock.

## Required context

- `AGENTS.md`
- `tests/test_lifecycle.py` (the failing test)
- `custom_components/windmill/coordinator.py` (`StartedJobRegistry`)
- `custom_components/windmill/const.py` (`MAX_TRACKED_JOBS`, `TRACKED_JOB_TTL_HOURS`)
- `docs/development/testing-strategy.md`

## Requirements

- The test controls the clock, using the `freezegun` fixture already used elsewhere in the
  suite for time-sensitive tests, rather than choosing timestamps that happen to be recent.
- The size bound and the age bound are each asserted, so that removing either rule from
  `StartedJobRegistry` fails a test.
- No production code changes: the pruning behaviour is correct as written.

## Acceptance criteria

- [ ] The test passes with the system clock set well after the fixture timestamps.
- [ ] Dropping the `MAX_TRACKED_JOBS` truncation from `StartedJobRegistry` fails a test.
- [ ] Dropping the `TRACKED_JOB_TTL_HOURS` pruning from `StartedJobRegistry` fails a test.
- [ ] The full suite passes: `uv run pytest -q --cov=custom_components.windmill
      --cov-report=term-missing --cov-fail-under=95`.

## Non-goals

- No change to `MAX_TRACKED_JOBS` or `TRACKED_JOB_TTL_HOURS`.
- No change to `StartedJobRegistry` behaviour.
- No sweep of other tests for the same pattern; if others are found, file them separately.

## Constraints

- Design the assertions through the registry's public interface, per `AGENTS.md`.

## Assumptions and research needs

| Item | Classification | Validation |
| --- | --- | --- |
| No other test in the suite has the same wall-clock dependency | assumption | The rest of the suite passed on 2026-08-03; re-check nearer any future TTL boundary |

## Validation evidence

Fill during implementation; do not pre-check.

| Check | Command or inspection | Result |
| --- | --- | --- |
| Repository guardrails | `uv run python scripts/validate_repository.py` | not run |
| Tests | `uv run pytest -q --cov=custom_components.windmill --cov-report=term-missing --cov-fail-under=95` | not run |

## Review evidence

- Reviewer/session:
- Findings:
- Resolution:

## Residual risks and follow-up

- None recorded

## Blog notes

- None
