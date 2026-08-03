---
id: WMHA-0037
title: Freeze time in the tracked job registry bound test
status: done
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

- [x] The test passes with the system clock set well after the fixture timestamps.
- [x] Dropping the `MAX_TRACKED_JOBS` truncation from `StartedJobRegistry` fails a test.
- [x] Dropping the `TRACKED_JOB_TTL_HOURS` pruning from `StartedJobRegistry` fails a test.
- [x] The full suite passes: `uv run pytest -q --cov=custom_components.windmill
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
| Interpreter | `uv run python -VV` | Python 3.14.6, as required |
| Repository guardrails | `uv run python scripts/validate_repository.py` | passed, 37 tickets checked |
| Tests | `uv run pytest -q --cov=custom_components.windmill --cov-report=term-missing --cov-fail-under=95` | passed, 401 passed, coverage 97.30% |
| Lint | `uv run ruff check custom_components tests` | passed |
| Format | `uv run ruff format --check custom_components tests` | passed, 31 files already formatted |
| Types | `uv run mypy custom_components/windmill` | passed, 16 source files |
| Clock independence | Full suite run at real time 2026-08-03 21:56 UTC, ~36 h after the frozen fixture instant `2026-08-02 10:00 UTC` and so past `TRACKED_JOB_TTL_HOURS` | passed; this is the exact condition that produced the reported failure |
| Size-bound mutation | Replaced `fresh[-MAX_TRACKED_JOBS:]` with `fresh` in `StartedJobRegistry._prune`, ran the suite, reverted | `test_registry_is_bounded_by_size_and_age` failed; 400 passed, 1 failed |
| Age-bound mutation | Replaced the `job.started_at > cutoff` filter with `list(self._jobs.values())` in `StartedJobRegistry._prune`, ran the suite, reverted | `test_registry_is_bounded_by_size_and_age` failed; 400 passed, 1 failed |

## Review evidence

- Reviewer/session: none. Low-risk, test-only change; `AGENTS.md` requires an independent
  review for medium- and high-risk work.
- Findings: n/a
- Resolution: n/a

## Residual risks and follow-up

- The assumption that no other test carries the same wall-clock dependency was not
  re-verified by inspection; the whole suite passing ~36 h past its newest fixture instant is
  indirect evidence only. The ticket's own non-goals exclude a sweep.
- `StartedJobRegistry.async_load` truncates with `rows[-MAX_TRACKED_JOBS:]` independently of
  `_prune`. Only the `_prune` truncation was mutation-tested; the load-path slice is not
  separately guarded by this test.

## Blog notes

- A time-dependent test that passes when written is worse than one that fails: this one kept
  reporting green while silently ceasing to check the size bound it existed to guard, because
  the age bound emptied the registry before the size assertion ran. Both bounds now have
  their own assertion, and each was confirmed by removing the corresponding production rule.
