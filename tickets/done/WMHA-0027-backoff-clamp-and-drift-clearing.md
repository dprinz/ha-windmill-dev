---
id: WMHA-0027
title: Fix rate-limit backoff clamp and worker-drift clearing on failed polls
status: done
type: quality
priority: high
risk: medium
created: 2026-08-02
updated: 2026-08-02
depends_on: [WMHA-0012]
---

# WMHA-0027: Fix rate-limit backoff clamp and worker-drift clearing on failed polls

## Outcome

A rate-limited long-interval coordinator never polls faster than its base interval, and a
transient failed worker poll no longer clears legitimate worker-drift repair issues.

## Context

Found by the independent WMHA-0012 diff review (2026-08-02), which was commissioned by the
WMHA-0015 release quality gate.

1. Medium — `custom_components/windmill/coordinator.py:128` computes
   `seconds = min(max(requested, base), MAX_RATE_LIMIT_BACKOFF_SECONDS)`. For coordinators
   whose base interval exceeds the 900 s cap (capability 6 h, update 6 h, runnable 30 min) a
   429 shrinks the interval to 15 min — polling 24x faster right after the server asked for
   slowing down. Empirically confirmed by the reviewer. Intended fix direction:
   `seconds = max(base, min(requested, MAX_RATE_LIMIT_BACKOFF_SECONDS))`.
2. Low — `custom_components/windmill/issues.py:105-115`: a failed worker poll yields an empty
   observation map, so every known drift group is popped, its issue deleted and the 30-minute
   grace timer restarted. A failed poll means "unknown", not "resolved". Intended fix
   direction: skip drift evaluation entirely when the poll failed.

## Acceptance criteria

- [x] A 429 on a long-interval coordinator never shortens its update interval below the base
      interval; covered by a test for a long-interval coordinator.
- [x] A failed worker poll leaves existing drift issues and their timers untouched; covered
      by a test.
- [x] Existing backoff and issue tests keep passing.

## Non-goals

- Persisting backoff state across reloads (recorded as an accepted observation).
- Adopting HA's native `UpdateFailed(retry_after=...)` (possible future simplification).

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
| Defect reproduction | New tests run against the pre-fix code (via `git stash`) | all 3 new tests failed on the old code, pass on the fix |

## Review evidence

- Reviewer/session: the independent WMHA-0012 diff review that found the defects
- Findings: medium backoff clamp, low drift clearing (see Context)
- Resolution: fixed in this ticket
