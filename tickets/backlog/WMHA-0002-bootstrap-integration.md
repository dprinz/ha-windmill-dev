---
id: WMHA-0002
title: Bootstrap the Home Assistant integration and config flow
status: backlog
type: feature
priority: high
risk: medium
created: 2026-08-01
updated: 2026-08-01
depends_on: [WMHA-0001]
---

# WMHA-0002: Bootstrap the Home Assistant integration and config flow

## Outcome

A user can install the custom integration, enter a Windmill base URL, workspace and token in Home Assistant's UI, and receive a correctly classified success, authentication error or connection error.

## Why

A validated config entry is the smallest production foundation for all later script, flow and job capabilities.

## Required context

- `AGENTS.md`
- `docs/product/vision.md`
- `docs/architecture/overview.md`
- accepted output of `WMHA-0001`
- current Home Assistant config-flow and testing documentation

## Requirements

- Home Assistant custom integration under `custom_components/windmill/`.
- Home Assistant-independent asynchronous Windmill API client boundary.
- UI config flow with unique-instance handling and no YAML requirement.
- Credentials stored only in config-entry data and excluded from logs/diagnostics.
- Automated tests for setup success and principal failure classes.

## Acceptance criteria

- [ ] Manifest and package structure pass the selected Home Assistant validation tooling.
- [ ] A config flow validates the connection using an endpoint established by `WMHA-0001`.
- [ ] Invalid authentication, unreachable instance and unexpected server response are distinct user-facing failures.
- [ ] Duplicate configuration is prevented using a stable non-secret identity.
- [ ] Setup, unload and reload behavior are covered through Home Assistant public interfaces.
- [ ] No script/flow execution or entities are included in this ticket.

## Non-goals

- Running scripts or flows.
- Discovering workspace contents.
- Job status entities or callbacks.
- Disabling TLS verification.

## Constraints

- Depends on an accepted API/authentication contract from `WMHA-0001`.
- Must preserve a path toward current Bronze quality requirements.

## Assumptions and research needs

| Item | Classification | Validation |
| --- | --- | --- |
| Suitable low-cost authentication validation endpoint exists | unresolved dependency | `WMHA-0001` |

## Validation evidence

| Check | Command or inspection | Result |
| --- | --- | --- |
| Repository guardrails | `python scripts/validate_repository.py` | not run |

## Review evidence

- Reviewer/session: not started
- Findings: not started
- Resolution: not started

## Residual risks and follow-up

- Ticket remains backlog until `WMHA-0001` is accepted.

## Blog notes

- Compare the assumed API contract with what the official schema and a real instance expose.
