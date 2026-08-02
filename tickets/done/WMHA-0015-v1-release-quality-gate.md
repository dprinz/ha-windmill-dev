---
id: WMHA-0015
title: Pass the first stable release quality gate
status: done
type: quality
priority: high
risk: high
created: 2026-08-01
updated: 2026-08-02
depends_on: [WMHA-0005, WMHA-0006, WMHA-0007, WMHA-0008, WMHA-0009, WMHA-0010, WMHA-0011, WMHA-0012, WMHA-0013, WMHA-0014]
---

# WMHA-0015: Pass the first stable release quality gate

## Outcome

The first stable release meets the documented v1 requirements, passes automated and manual validation, and has an evidence-based compatibility statement.

## Why

A collection of completed feature tickets does not by itself prove that installation, upgrades, partial permissions and real-instance behavior work together.

## Required context

- `AGENTS.md`
- `docs/product/requirements.md`
- all completed v1 tickets, ADRs and research notes

## Requirements

- End-to-end testing against supported Home Assistant and Windmill combinations.
- Upgrade, reload, removal and credential-rotation tests.
- Security, privacy, performance and recorder-impact review.
- Final traceability review for every v1 requirement.

## Acceptance criteria

- [x] Every PR-001 through PR-014 requirement is implemented, deferred explicitly or removed by a reviewed product decision. — `docs/development/v1-traceability-matrix.md`; no undocumented gaps found.
- [x] CI, lint, type, translation, HACS and full test suites pass. — see validation evidence; CI runs 30758630293 and 30758630322 green on `main` at `ede5b0a` (2026-08-02).
- [x] Real-instance smoke tests cover at least one supported self-hosted version and document Cloud coverage or its absence. — client-level smoke against disposable local CE `v1.775.2` passed on 2026-08-02 (execution, cancellation, capability discovery, update check); Cloud coverage is absent and published as a release risk in `docs/product/supported-versions-and-limitations.md`.
- [x] Partial-permission configurations load and degrade as designed. — proven by capability/worker/health tests (403/404 degradation) and by the live five-state capability discovery (execution/cancellation correctly `not_applicable` before target selection); live restricted-token verification remains follow-up WMHA-0026.
- [x] No secret or sensitive job payload appears in logs, state or diagnostics. — systematic review 2026-08-02: header-only token (`api.py:721`), public probes send no token, strict job allowlist parsing, redacted allowlist diagnostics, 7 log statements carry no secrets, sentinel tests in `tests/test_api.py`/`tests/test_diagnostics.py`.
- [x] Known limitations and supported versions are published before release approval. — `docs/product/supported-versions-and-limitations.md`, linked from the README.

## Non-goals

- Implementing post-v1 push observation.
- Publishing the release without explicit human approval.

## Validation evidence

| Check | Command or inspection | Result |
| --- | --- | --- |
| Repository guardrails | `python scripts/validate_repository.py` | passed, 26 tickets checked, 2026-08-02 |
| Full release matrix | `uv run pytest -q --cov=custom_components.windmill --cov-report=term-missing --cov-fail-under=95` | 385 passed, 97.28% branch coverage, 2026-08-02; after the WMHA-0027/WMHA-0028 review fixes: 390 passed, 97.28% (evidence in those tickets; not rerun here — this finalization touches no production code) |
| Lint | `uv run ruff check custom_components tests` | passed, 2026-08-02 |
| Format | `uv run ruff format --check custom_components tests` | 31 files already formatted, 2026-08-02 |
| Types | `uv run mypy custom_components/windmill` | no issues in 16 source files (strict), 2026-08-02 |
| Lockfile | `uv lock --check` | passed, 2026-08-02 |
| Whitespace | `git diff --check` | passed, 2026-08-02 |
| CI on `main` | `gh run list` | Both workflows success on `ede5b0a` (runs 30758630293, 30758630322, 2026-08-02). On `050aac4`: Validate HACS and hassfest success (run 30762685435); Repository guardrails run 30762685452 failed only because this ticket sat in `tickets/in-progress/` with frontmatter status `backlog` in the pushed commits — an uncommitted-state artifact of this ticket's own finalization, resolved by moving it to `tickets/done/` with status `done`; the guardrail check passes locally with the finalized state |
| Traceability | `docs/development/v1-traceability-matrix.md` | PR-001..PR-014 all implemented or explicitly deferred with evidence; no undocumented gap |
| Lifecycle coverage | inspection of `tests/test_init.py`, `tests/test_config_flow.py`, `tests/test_lifecycle.py` | reload, removal (incl. store deletion, cross-entry isolation, failing-delete tolerance), reauth/reconfigure/options and legacy-entry defaults all covered; both stores are version 1, so no migration test applies to v1; no additions needed |
| Security/privacy/recorder review | grep/read of `api.py`, `diagnostics.py`, `event.py`, `coordinator.py`, `issues.py`, `system_health.py` | no token in logs/state/diagnostics/URLs; bounded event attributes (5 fields); no per-job entities; bounded intervals (health/runs 60 s, workers 2 min, runnables 30 min, capability/update 6 h) and bounds (3×100 jobs/poll, 200 seen IDs, 50 tracked jobs/24 h, ≤500 workers, 25 selections); rate-limit backoff 300–900 s |
| Live smoke | disposable local Windmill CE `v1.775.2` via official docker-compose, client-level script driving the integration's own client | PASS, 2026-08-02: public no-token probes, whoami, five-state capability discovery, detailed health, worker groups/workers, live `/api/uptodate` (`v1.775.2` → `v1.776.0`), script execution observed `success`, cancellation observed `canceled`; containers/volumes/images removed afterwards; one transient 404 when running a script in the same second it was created (upstream propagation race, cleanly typed error) |
| Cloud coverage | — | absent; no Cloud test tenant exists; published as release risk; follow-up WMHA-0026 |

## Review evidence

- Reviewer/session: independent gate review, 2026-08-02 — verdict **changes requested**: 1 Major, 3 Minor, 2 Notes.
- Findings:
  - Major 1: the process deviation recorded in `docs/development/handoff-after-WMHA-0012.md` (high-risk WMHA-0012 never received an independent review) was unaddressed by this gate.
  - Minor 2: internal contradiction in `docs/development/v1-traceability-matrix.md` — PR-010 row said "implemented with live gap" while the live-checks section said the smoke closed it.
  - Minor 3: "seven body shapes" in the PR-010 evidence was not reproducible (`tests/test_api.py:1119` parametrizes four shapes, plus unparseable-text and missing-endpoint tests).
  - Minor 4: token header citation said `api.py:720`; the correct line is `api.py:721`.
  - Note 6 (carried): the WMHA-0018 same-millisecond residual was missing from the public limitations document.
- Resolution:
  - Major 1 closed: an independent WMHA-0012 diff review was performed after this gate review. Verdict: WMHA-0012 is release-worthy in substance and its security parts are clean; it surfaced one Medium defect (the rate-limit backoff clamp shortened long polling intervals after a 429) and two Low findings (worker-drift issues cleared on a failed poll; diagnostics reported static instead of effective feature defaults). The Medium and the drift finding were fixed in WMHA-0027 (`tickets/done/WMHA-0027-backoff-clamp-and-drift-clearing.md`, commit `3b91afc`), the diagnostics-defaults finding in WMHA-0028 (`tickets/done/WMHA-0028-diagnostics-feature-defaults.md`, commit `050aac4`); both pushed, 390 tests green.
  - Minor 2 fixed: PR-010 row now reads "implemented" and cites the live `/api/uptodate` observation.
  - Minor 3 fixed: the evidence now names four parametrized shapes plus the unparseable-text and missing-endpoint tests.
  - Minor 4 fixed: citation corrected to `api.py:721`.
  - Note 6 fixed: same-millisecond event behavior added as limitation 10 in `docs/product/supported-versions-and-limitations.md`.

## Handoff notes for the reviewer

- Start from `docs/development/v1-traceability-matrix.md`, then this ticket's diff, then `docs/product/supported-versions-and-limitations.md`.
- The smoke test was client-level, not a full Home Assistant end-to-end run; that boundary is deliberate and documented.
- The smoke used a superadmin session token on a disposable instance; least-privilege live behavior is follow-up ticket WMHA-0026.
- The 400s in the smoke log on script creation are re-run conflicts on the persistent throwaway instance, not failures (scripts existed from the first run).
