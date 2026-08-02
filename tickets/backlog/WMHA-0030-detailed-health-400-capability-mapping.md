---
id: WMHA-0030
title: Map detailed-health 400 for granular-scoped tokens to the right capability state
status: backlog
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

- [ ] Capability discovery for detailed health with a granular-scoped token reports a state
      whose reason matches the observed upstream cause, or a documented decision keeps the
      current mapping.
- [ ] Existing capability and error-mapping tests stay green; new behavior is test-covered.

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
| Repository guardrails | `python scripts/validate_repository.py` | not run |

## Review evidence

- Reviewer/session: not started
- Findings: not started
- Resolution: not started
