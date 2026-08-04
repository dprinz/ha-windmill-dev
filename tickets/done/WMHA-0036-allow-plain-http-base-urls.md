---
id: WMHA-0036
title: Allow plain HTTP base URLs with a visible transport warning
status: done
type: feature
priority: high
risk: medium
created: 2026-08-03
updated: 2026-08-04
depends_on: []
---

# WMHA-0036: Allow plain HTTP base URLs with a visible transport warning

## Outcome

A user can configure a self-hosted Windmill instance reachable only over plain HTTP — for
example `http://windmill.home.arpa:8000/` — and the config flow accepts it. When the
resulting base URL is HTTP and the host is not a loopback address, Home Assistant shows a
non-fixable repair issue explaining that the Windmill token is transmitted unencrypted.

## Why

Reported by the repository owner on 2026-08-03. Entering `http://windmill.home.arpa:8000/`
in the config flow fails with `invalid_url`:

> Gib eine gültige HTTPS-URL ein. HTTP ist nur für Loopback-Adressen erlaubt.

`normalize_base_url` in `custom_components/windmill/api.py` rejects HTTP for every host
that is not loopback. That rule blocks the common self-hosted deployment: a Windmill
container on the LAN behind a local DNS name, with no certificate. The hostname cannot be
classified as private at validation time — `home.arpa` resolves only through the user's own
resolver — so no heuristic can distinguish "LAN host" from "public host" here.

The previous rule traded a real, frequent deployment for a protection the user can already
reason about. The decision recorded with the human on 2026-08-03 is to accept HTTP and make
the cost visible rather than to keep refusing it.

## Required context

- `AGENTS.md`
- `custom_components/windmill/api.py` (`normalize_base_url`, `_is_loopback`)
- `custom_components/windmill/issues.py`
- `custom_components/windmill/__init__.py` (issue wiring)
- `custom_components/windmill/strings.json` and `translations/{en,de}.json`
- `tests/test_api.py`, `tests/test_config_flow.py`, `tests/test_issues.py`

## Requirements

- `normalize_base_url` accepts `http` for any host and keeps every other validation rule
  unchanged: no credentials, no query, no fragment, no unsafe path segment, IDNA host,
  port and case normalization.
- The transport classification is exposed by the transport module, not re-derived in the
  Home Assistant layer.
- A config entry whose base URL is HTTP on a non-loopback host owns one repair issue with
  translation key `insecure_transport`, severity `warning`, `is_fixable: false`.
- Loopback HTTP produces no issue: nothing leaves the host.
- The issue is deleted when the entry is reconfigured to HTTPS, through the existing
  re-evaluation path.
- The `invalid_url` config-flow error and the `base_url` field description no longer claim
  that HTTP is restricted to loopback.

## Acceptance criteria

- [x] `normalize_base_url("http://windmill.home.arpa:8000/")` returns
      `http://windmill.home.arpa:8000`.
- [x] Every other rejection case in `test_reject_unsafe_base_url` still raises
      `WindmillUrlError`.
- [x] The config flow completes for an HTTP base URL on a non-loopback host.
- [x] Setting up an entry with an HTTP non-loopback base URL creates exactly one
      `insecure_transport` issue carrying the host as a placeholder.
- [x] Setting up an entry with `http://localhost:8000` or `https://…` creates no
      `insecure_transport` issue.
- [x] `strings.json`, `translations/en.json` and `translations/de.json` carry the new issue
      text and the corrected `invalid_url` / `base_url` strings, with identical key sets.
- [x] The full test suite, lint and type check pass.

## Non-goals

- No opt-in checkbox or option to re-enable strict HTTPS enforcement. The decision is that
  HTTP is allowed unconditionally and the warning carries the risk signal.
- No change to TLS verification for HTTPS connections. Certificate validation stays on.
- No attempt to classify a hostname as private or public by resolution or by suffix.
- No change to token storage, redaction or diagnostics.

## Constraints

- The token must not appear in the issue title, description or placeholders.
- `AGENTS.md` forbids silently weakening input validation. This ticket is the record of the
  deliberate, human-approved relaxation; the warning is the compensating control.
- Existing config entries are unaffected: no migration, no re-validation on upgrade.

## Assumptions and research needs

| Item | Classification | Validation |
| --- | --- | --- |
| `runtime.client.base_url` is the normalized URL available to `async_evaluate_issues` | assumption | Read `api.py:475` and `models.py`; confirmed |
| Home Assistant renders `ir.async_create_issue` placeholders in the issue description | fact | Existing `worker_version_drift` issue uses the same mechanism |

## Validation evidence

Fill during implementation; do not pre-check.

Run on 2026-08-03 with `uv run python -VV` reporting CPython 3.14.6.

| Check | Command or inspection | Result |
| --- | --- | --- |
| Repository guardrails | `uv run python scripts/validate_repository.py` | pass — 36 tickets checked |
| Tests and coverage | `uv run pytest -q --cov=custom_components.windmill --cov-report=term-missing --cov-fail-under=95` | 400 passed, 1 failed, 97.30% total coverage, `issues.py` at 100%. The single failure is `tests/test_lifecycle.py::test_registry_is_bounded_by_size_and_age` and is **pre-existing**: verified by `git stash -u` and re-running the file on unmodified `master`, where it fails identically. See residual risks. |
| Lint | `uv run ruff check custom_components tests` | pass |
| Format | `uv run ruff format --check custom_components tests` | pass — 31 files already formatted |
| Type check | `uv run mypy custom_components/windmill` | pass — no issues in 16 source files |
| Translation key parity | Recursive key-set comparison of `strings.json` against `translations/en.json` and `translations/de.json` | identical in both |
| Reported symptom | `normalize_base_url("http://windmill.home.arpa:8000/")` | returns `http://windmill.home.arpa:8000`; covered by `tests/test_api.py::test_normalize_base_url` |

Re-run on 2026-08-04 in the review session, after `WMHA-0037` removed the time-dependent
failure recorded above:

| Check | Command or inspection | Result |
| --- | --- | --- |
| Tests and coverage | `uv run pytest -q --cov=custom_components.windmill --cov-report=term-missing --cov-fail-under=95` | 406 passed, 0 failed, 97.30% total coverage; `issues.py` at 100% |
| Lint, format, types | `uv run ruff check`, `uv run ruff format --check`, `uv run mypy custom_components/windmill` | all pass; 31 files formatted, 16 source files clean |

## Review evidence

- Reviewer/session: independent review on 2026-08-04 in a fresh session that did not
  implement the change. Read the ticket and the `0371425` diff before the implementer's
  narrative.
- Findings: the relaxation is exactly one deleted rule in `normalize_base_url` — the
  `scheme == "http" and not _is_loopback(host)` rejection. Every other structural rule
  (scheme allowlist, host requirement, credential and query rejection, path normalization)
  is untouched, and no TLS or certificate handling is involved anywhere in the diff, so
  HTTPS connections keep verifying. The compensating control is real and correctly scoped:
  `is_insecure_transport` reproduces the deleted predicate, `_async_insecure_transport_issue`
  runs on every issue evaluation, and it deletes the issue when the condition stops holding
  rather than leaving it stale. The placeholder carries `urlsplit(base_url).hostname` only —
  no token, no path, no query — which matches the constraint. Loopback stays exempt in both
  the warning and the reasoning. No finding that blocks completion.
- Resolution: accepted as implemented. The advisory-not-enforcing nature of the warning is
  the recorded human decision, not a review finding.

## Residual risks and follow-up

- **The warning is advisory, not enforcing.** Nothing stops a user from pointing the
  integration at a public HTTP host and dismissing the repair issue. That is the accepted
  trade-off recorded above, not an oversight.
- **HTTP is not detectable as "LAN only".** `is_insecure_transport` treats every
  non-loopback HTTP host identically, including RFC 1918 addresses. A user on a trusted LAN
  sees the same warning as one crossing the internet. Narrowing this would need name
  resolution at validation time, which the config flow deliberately does not do.
- **No ADR yet.** The HTTPS-only rule was never recorded as an accepted decision, so nothing
  needed superseding. If the transport policy is revisited again, promote it to an ADR
  rather than to a third ticket.
- **Out of scope, observed while validating:**
  `tests/test_lifecycle.py::test_registry_is_bounded_by_size_and_age` fails on unmodified
  `master` as well. The test builds tracked jobs at fixed 2026-08-02 timestamps and asserts
  against `MAX_TRACKED_JOBS`, but `StartedJobRegistry` also prunes by `TRACKED_JOB_TTL_HOURS`
  against real wall-clock time. Every fixture job is now older than the TTL, so the registry
  is empty and the assertion reports `0 == 50`. The production pruning is behaving correctly;
  the test is time-dependent and rots as the clock advances. It needs `freezegun` like the
  other time-sensitive tests. This requires its own ticket. **Closed** by `WMHA-0037`
  (`6cc2468`); the suite is green as of 2026-08-04.
- Also still open from WMHA-0035: `.python-version` resolving to a pre-release interpreter.
  It did not reproduce in this session — `uv run python -VV` reported CPython 3.14.6.

## Blog notes

- A validation rule that cannot be satisfied by a legitimate deployment is not a security
  control; it is a support ticket. Refusing `http://windmill.home.arpa:8000` protected
  nobody — the user's only paths forward were to abandon the integration or to be told their
  LAN setup was unsupported. Moving the constraint from the validator to a repair issue kept
  the information (the token is in the clear) while removing the dead end. The signal
  survives; the wall does not.
- The hostname is the reason the strict rule could not simply be narrowed. `home.arpa`
  resolves only through the user's own resolver, so at validation time it is
  indistinguishable from a public name. Any "allow private networks only" heuristic would
  have had to resolve DNS inside the config flow — more I/O, more failure modes, and still
  wrong for split-horizon setups.
