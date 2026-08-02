---
id: WMHA-0033
title: Align the guardrail workflow interpreter with the supported Python
status: done
type: chore
priority: low
risk: low
created: 2026-08-03
updated: 2026-08-03
depends_on: []
---

# WMHA-0033: Align the guardrail workflow interpreter with the supported Python

## Outcome

Every place in the repository that names a Python version names the supported one, so no reader or
agent can conclude from CI that 3.13 is a supported interpreter.

## Why

Found by the review of tickets WMHA-0013 to WMHA-0030 on 2026-08-03.

`.github/workflows/repository-guardrails.yml:21` pins `python-version: "3.13"`, while
`pyproject.toml` requires `>=3.14.2` and Home Assistant 2026.7.4 sets `REQUIRED_PYTHON_VER` to
`(3, 14, 2)`. The workflow itself is correct in practice — `scripts/validate_repository.py` imports
only `json`, `re`, `sys` and `pathlib` — but the mismatch is one of the sources of the recurring
confusion about which interpreter is authoritative, which `AGENTS.md` now addresses in
"Toolchain and versions".

The concrete failure mode this prevents: production code uses Python 3.14 exception syntax
(`custom_components/windmill/coordinator.py:536`), which an older interpreter rejects with
`SyntaxError: multiple exception types must be parenthesized`. Anything in the repository that
suggests an older interpreter is fine invites that misdiagnosis.

## Required context

- `AGENTS.md` (section "Toolchain and versions")
- `.github/workflows/repository-guardrails.yml`
- `.python-version`, `pyproject.toml`
- `scripts/validate_repository.py`

## Requirements

- Use the supported Python version in the guardrail workflow, resolved from the repository pin where
  the action supports it rather than hard-coded a second time.
- Keep `scripts/validate_repository.py` standard-library only, so it stays runnable on any
  interpreter; that property is deliberate and documented in `AGENTS.md`.

## Acceptance criteria

- [x] The guardrail workflow runs on the Python version named in `AGENTS.md`. It now reads
      `python-version-file: .python-version` instead of a literal, so the pin has one home.
- [x] No repository file names a Python version that contradicts `pyproject.toml` and
      `.python-version`; verified by inspection of workflows, documentation and configuration.
      `grep -rn "3\.13\|3\.12\|python-version"` over workflows, `*.toml`, `*.md` and `*.json`
      leaves only `AGENTS.md`, where 3.13 appears as the *counter-example* in the wrong-interpreter
      section, and this ticket. `release.yml` and `validate-hacs.yml` name no Python version.
- [x] The guardrail workflow still succeeds on `main`; the run identifier is recorded.
      (See validation evidence.)
- [x] `scripts/validate_repository.py` still imports only the standard library: `json`, `re`, `sys`,
      `pathlib` and `__future__`.

## Non-goals

- Adding test, lint or type jobs to CI; that is `WMHA-0031`, which may absorb this change.
- Changing the guardrail script's behavior.

## Constraints

- Do not weaken the existing workflow permissions or unpin any action.

## Assumptions and research needs

| Item | Classification | Validation |
| --- | --- | --- |
| The runner image offers Python 3.14.2 or newer through the chosen setup action | assumption | Verify in the workflow run before closing |

## Validation evidence

| Check | Command or inspection | Result |
| --- | --- | --- |
| Repository guardrails | `python scripts/validate_repository.py` | 2026-08-03: passed (34 tickets checked) |
| Workflow still parses and keeps its permissions | `yaml.safe_load` of the workflow | 2026-08-03: `permissions: {contents: read}` unchanged, three steps unchanged, `with: {python-version-file: .python-version}` |
| Standard library only | imports of `scripts/validate_repository.py` | 2026-08-03: `json`, `re`, `sys`, `pathlib` |
| No contradicting version left | `grep -rn "3\.13\|3\.12\|python-version"` over workflows, toml, md, json | 2026-08-03: only `AGENTS.md`'s counter-example and this ticket |
| Guardrail workflow on `main` | `gh run view 30772299845` after commit `fcfc93c` | 2026-08-03: success. The log shows "Resolved .python-version as 3.14" and "Successfully set up CPython (3.14.6)" — the runner offers a supported interpreter, closing the ticket's open assumption |

## Review evidence

- Reviewer/session: implementing session (Claude Code `b3e36412`, 2026-08-03). Low risk, so
  `AGENTS.md` requires no independent review.
- Findings: one observation, out of scope here. `release.yml` runs `python scripts/build_release.py`
  on the runner's default interpreter without a `setup-python` step, so it names no version but
  also pins none. `build_release.py` would have to be standard-library only for that to be safe;
  `WMHA-0031` touches CI next and can absorb the check.
- Resolution: the guardrail workflow now resolves its interpreter from `.python-version`; no other
  change was needed.

## Residual risks and follow-up

- None recorded

## Blog notes

- None
