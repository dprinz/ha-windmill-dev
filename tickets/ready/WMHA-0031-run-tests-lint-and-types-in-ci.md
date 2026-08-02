---
id: WMHA-0031
title: Run the test suite, lint and type check in CI
status: ready
type: delivery
priority: high
risk: low
created: 2026-08-03
updated: 2026-08-03
depends_on: [WMHA-0014]
---

# WMHA-0031: Run the test suite, lint and type check in CI

## Outcome

A push or pull request against `main` fails when the test suite, coverage threshold, lint, format
or type check fails. The green checkmark on `main` proves the same thing the tickets claim.

## Why

Found by the review of tickets WMHA-0013 to WMHA-0030 on 2026-08-03.

The repository has three workflows: `repository-guardrails.yml` (structure and translation
guardrails only), `validate-hacs.yml` (HACS action and hassfest) and `release.yml`. None of them
runs `pytest`, `ruff` or `mypy` — verified with `grep -rn "pytest\|mypy\|ruff" .github/`, which
returns nothing.

Two consequences:

1. Every test result recorded in the validation-evidence tables of WMHA-0013 to WMHA-0030 is a
   local-machine result. Nothing reproduces it on a clean checkout.
2. `WMHA-0015` acceptance criterion 2 reads "CI, lint, type, translation, HACS and full test suites
   pass" and cites CI run IDs as evidence. Those runs prove the guardrail and HACS jobs only. The
   criterion is broader than the evidence behind it.

A regression pushed to `main` today is caught by no automated check.

## Required context

- `AGENTS.md` (sections "Toolchain and versions" and "Validation")
- `docs/development/testing-strategy.md`
- `.github/workflows/repository-guardrails.yml`
- `pyproject.toml`
- `../done/WMHA-0014-hacs-and-release-automation.md`, `../done/WMHA-0015-v1-release-quality-gate.md`

## Requirements

- Run the exact command list from `docs/development/testing-strategy.md` in CI, on the pinned
  Python version, with the same coverage threshold the tickets record.
- Install dependencies from the lockfile, and fail when the lockfile is stale (`uv lock --check`).
- Keep workflow permissions minimal and pin third-party actions by full commit SHA, matching the
  security model `WMHA-0014` established for the existing workflows.
- Do not weaken any existing check to make the new job green.

## Acceptance criteria

- [ ] A push and a pull request against `main` run the full test suite with the coverage threshold,
      `ruff check`, `ruff format --check`, `mypy` and `uv lock --check`.
- [ ] The job runs on the Python version named in `AGENTS.md`, resolved from the repository pin
      rather than hard-coded in a second place that can drift.
- [ ] A deliberately broken commit (one failing test, one lint error, one type error, each tried
      separately) fails the workflow; the evidence records the run or the local equivalent.
- [ ] Third-party actions are pinned by commit SHA and job permissions are the minimum required.
- [ ] `docs/development/testing-strategy.md` states that CI enforces these commands.

## Non-goals

- Changing any test, lint rule or type annotation to make CI pass.
- Adding a matrix over several Python or Home Assistant versions; the project pins exactly one of
  each.
- Retroactively correcting the evidence tables of tickets in `tickets/done/`, which is append-only.

## Constraints

- The workflow must not need repository secrets, and must never contact a real Windmill instance.
- Keep the runtime acceptable: the suite currently completes in about six seconds locally.

## Assumptions and research needs

| Item | Classification | Validation |
| --- | --- | --- |
| A GitHub-hosted runner can provide Python 3.14.2 or newer through `astral-sh/setup-uv` or `actions/setup-python` | assumption | Verify against the current runner images before pinning the approach |

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

- `WMHA-0033` covers the interpreter version of the existing guardrail workflow and can be done in
  the same change if that is simpler.

## Blog notes

- Candidate: a release quality gate that cites CI run identifiers proves only what those runs
  actually executed. Naming the job, not the workflow, is the difference.
