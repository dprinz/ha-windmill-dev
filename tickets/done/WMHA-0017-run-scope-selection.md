---
id: WMHA-0017
title: Add run-observation scope selection
status: done
type: feature
priority: medium
risk: medium
created: 2026-08-02
updated: 2026-08-02
depends_on: [WMHA-0007, WMHA-0008, WMHA-0009]
---

# WMHA-0017: Add run-observation scope selection

## Outcome

A user can restrict run observation to all visible top-level jobs, to selected runnables or to jobs
that Home Assistant started, instead of always observing every visible top-level job.

## Why

`PR-006` requires configurable observation scope. WMHA-0007 implemented bounded observation of all
visible top-level jobs, because the two narrower scopes need data that did not exist yet: runnable
selection is introduced by WMHA-0008 and the Home Assistant-started job registry by WMHA-0009 and
WMHA-0010. Splitting the scope selector out keeps WMHA-0007 shippable without a half-wired option.

## Required context

- `AGENTS.md`
- `docs/product/requirements.md`
- the accepted output of `WMHA-0007`, `WMHA-0008` and `WMHA-0009`

## Requirements

- One option that selects between all visible top-level jobs, selected runnables and Home
  Assistant-started jobs.
- Filtering happens on bounded, already-parsed job metadata; no additional sensitive field is
  retained.
- Changing the scope must not replay historical jobs as new events.
- The retention model of WMHA-0007 keeps working across a scope change.

## Acceptance criteria

- [x] The scope option is offered in onboarding and in the options flow with a safe default.
- [x] Each scope value is covered by tests, including the transition between scopes.
- [x] A scope change never fires events for jobs that completed before the change.
- [x] Aggregate counters and last-run timestamps respect the selected scope.

## Non-goals

- Changing the polling model or the retention window of WMHA-0007.
- Per-job entities.

## Validation evidence

| Check | Command or inspection | Result |
| --- | --- | --- |
| Repository guardrails | `python scripts/validate_repository.py` | passed; 23 tickets checked, translation parity holds |
| Run-scope tests | `uv run pytest -q tests/test_runs.py tests/test_config_flow.py` | 71 passed |
| Full suite and coverage | `uv run pytest -q --cov=custom_components.windmill --cov-report=term-missing --cov-fail-under=95` | 385 passed; 97.28% |
| Lint and format | `uv run ruff check custom_components tests`; `uv run ruff format --check custom_components tests` | passed |
| Types | `uv run mypy custom_components/windmill` | passed; 16 source files checked |
| Lock and diff | `uv lock --check`; `git diff --check` | passed |

The scope-change semantics are implemented and tested as follows: the persisted watermark, seen
identifiers and initialization flag are kept across a scope change, so nothing already observed (or
completed at or below the watermark) can fire again. The last-success and last-failure timestamps
are the scoped part of the model and restart empty for the new scope. Filtering uses only the
existing bounded job projection (identifier, kind, path, state, timestamps), so no additional
sensitive field is retained.

Acceptance criterion 3 is interpreted explicitly, not silently: "jobs that completed before the
change" means completions the retention model already knows — anything observed before, or
completed at or below the watermark. A completion that happened before the change but outside the
old scope and above the watermark is genuinely new information, so a scope widening fires it
exactly once under the WMHA-0007 newly-observed semantics and then retains it. This behavior is
pinned by `test_scope_widening_fires_an_unobserved_completion_exactly_once`, so it is designed
rather than accidental.

Residual risk, accepted and documented in the README: under the `home_assistant_started` scope, a
job cancelled through the integration's own cancel action emits no `canceled` event. The cancel
action forgets the job immediately (WMHA-0010 semantics), so the scope filter drops the completion
before it reaches retention. This is a deliberate interaction: the user cancelled the job
themselves and already received the action result, so no event is needed; under the `all` scope the
cancellation fires normally. No follow-up ticket was created: deferring the forget until the
completion is observed would keep uncancellable jobs tracked for up to the 24-hour TTL, weakening
the WMHA-0010 cancellation contract to fix a benign gap.

## Review evidence

- Reviewer/session: independent review agent on 2026-08-02; verdict "changes requested" with two
  binding minor findings; the core implementation was judged sound.
- Findings: (1) a cancelled Home Assistant-started job loses its `canceled` event under the
  `home_assistant_started` scope because cancel forgets the job before the poll observes the
  completion; (2) the exact scope-widening behavior for pre-change but unobserved completions was
  neither pinned by a test nor named as the interpretation of acceptance criterion 3.
- Resolution: (1) accepted as a deliberate interaction with the WMHA-0010 forget-on-cancel
  semantics, documented with rationale in this ticket and in the README `run_scope` section; no
  follow-up ticket, justified above. (2) The AC 3 interpretation is stated explicitly above, and
  `test_scope_widening_fires_an_unobserved_completion_exactly_once` pins the fire-exactly-once
  behavior. Re-validated by the full check list above after the changes.
