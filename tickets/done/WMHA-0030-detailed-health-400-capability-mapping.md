---
id: WMHA-0030
title: Map detailed-health 400 for granular-scoped tokens to the right capability state
status: done
type: quality
priority: low
risk: low
created: 2026-08-02
updated: 2026-08-02
depends_on: [WMHA-0026]
---

# WMHA-0030: Map detailed-health 400 for granular-scoped tokens to the right capability state

## Outcome

When a granular-scoped token probes `GET /api/health/detailed`, capability discovery reports
a state that reflects the real cause (token scope cannot address the route) instead of
`unsupported/unexpected_response`, or a reviewed decision documents why the current mapping
is acceptable.

## Why

Live verification on 2026-08-02 (WMHA-0026, disposable CE `v1.775.2`) showed that Windmill's
scope middleware rejects granular-scoped tokens on `/api/health/detailed` with `400` and the
body "Could not extract domain from route: /api/health/detailed" — not the `401`/`403` the
client taxonomy expects for authorization failures. The client maps `400` to
`WindmillRequestError`, so capability discovery reports `unsupported/unexpected_response`.
Users with a correctly least-privileged token see detailed health as "unsupported" (endpoint
missing) rather than "unauthorized" (token scope), which can mislead onboarding and
diagnostics. Impact is cosmetic: the feature disables itself gracefully as designed.

## Decision

Map exactly this case to `unauthorized`/`permission_denied` — no new reason, no doc-only
keep, no generic 400 remapping.

Rationale: the detailed-health probe is a fixed, parameterless authenticated GET, so a `400`
on it cannot be caused by the client's request shape. The pinned v1.775.2 source (no `health`
scope domain) plus the WMHA-0026 live verification make the scope middleware the only known
producer of this `400`, which is an authorization/scope failure in substance. The existing
five-state lattice already expresses it: `unauthorized`/`permission_denied` is the same
state/reason a `403` yields, the setup copy already defines `unauthorized` as "the token
lacks that permission", and the option description already says detailed health "needs a
token that Windmill accepts on the detailed health endpoint". A new `CapabilityReason` would
add churn to diagnostics and translations without telling the user anything more actionable.

Implementation: `_probe_json_object` gained an opt-in `scope_denied_statuses` parameter;
only the detailed-health probe passes `frozenset({400})`, which raises
`WindmillAuthorizationError` before the generic status mapping. The response body is never
read for non-success statuses (the transport already discards it), so no body parsing was
added and the denylist policy is untouched. `WindmillRequestError` handling elsewhere —
including `400` on every other probe — still maps to `unsupported`/`unexpected_response`,
covered by a regression test.

## Required context

- `AGENTS.md`
- `docs/research/windmill-api-contract.md` (2026-08-02 WMHA-0026 verification note)
- `custom_components/windmill/api.py` (`_probe`, `_probe_json_object`, error taxonomy)
- `tests/test_capabilities.py`, `tests/test_api.py`

## Requirements

- Decide whether a `400` on this specific probe (or the specific upstream body) should map
  to `unauthorized`, to a new precise reason, or stay as-is with documentation.
- If the mapping changes, cover it with mocked tests at the existing probe seams; do not
  widen response-body parsing beyond the sensitive-data denylist policy.

## Acceptance criteria

- [x] Capability discovery for detailed health with a granular-scoped token reports a state
      whose reason matches the observed upstream cause, or a documented decision keeps the
      current mapping.
- [x] Existing capability and error-mapping tests stay green; new behavior is test-covered.

## Non-goals

- Changing the detailed-health feature itself or requiring broader tokens.
- Generic remapping of all `400` responses.

## Constraints

- Do not deserialize arbitrary server error bodies into entity state or diagnostics.

## Assumptions and research needs

| Item | Classification | Validation |
| --- | --- | --- |
| The `400` status with this body is stable across supported versions | assumption | repeat probe when the compatibility floor changes |

## Validation evidence

Fill during implementation; do not pre-check.

| Check | Command or inspection | Result |
| --- | --- | --- |
| Tests + coverage | `uv run pytest -q --cov=custom_components.windmill --cov-report=term-missing --cov-fail-under=95` | 392 passed, total coverage 97.28% (threshold 95%) |
| Lint | `uv run ruff check custom_components tests` | All checks passed |
| Format | `uv run ruff format --check custom_components tests` | 31 files already formatted |
| Types | `uv run mypy custom_components/windmill` | Success: no issues found in 16 source files |
| Lockfile | `uv lock --check` | Resolved 158 packages, lock consistent |
| Repository guardrails | `python scripts/validate_repository.py` | Repository validation passed (30 tickets checked) |
| Diff hygiene | `git diff --check` | no output (clean) |

New tests in `tests/test_capabilities.py`: `detailed_status=400` maps to
`unauthorized`/`permission_denied`; `workers_status=400` still maps to
`unsupported`/`unexpected_response` (no generic 400 remapping). Both run mocked at the
existing `aioclient_mock` probe seam, no network.

## Review evidence

- Reviewer/session: implementing session, self-review against ticket and diff (risk: low —
  per AGENTS.md no independent review required for low-risk work)
- Findings: mapping is scoped to the detailed-health probe only; error-body parsing not
  widened; strings/issue flows already handle `unauthorized` for this capability; user-facing
  limitation doc updated
- Resolution: no open findings
