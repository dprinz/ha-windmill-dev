---
id: WMHA-0015
title: Pass the first stable release quality gate
status: backlog
type: quality
priority: high
risk: high
created: 2026-08-01
updated: 2026-08-01
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

- [ ] Every PR-001 through PR-014 requirement is implemented, deferred explicitly or removed by a reviewed product decision.
- [ ] CI, lint, type, translation, HACS and full test suites pass.
- [ ] Real-instance smoke tests cover at least one supported self-hosted version and document Cloud coverage or its absence.
- [ ] Partial-permission configurations load and degrade as designed.
- [ ] No secret or sensitive job payload appears in logs, state or diagnostics.
- [ ] Known limitations and supported versions are published before release approval.

## Non-goals

- Implementing post-v1 push observation.
- Publishing the release without explicit human approval.

## Validation evidence

| Check | Command or inspection | Result |
| --- | --- | --- |
| Repository guardrails | `python scripts/validate_repository.py` | not run |
| Full release matrix | documented release commands | not run |

## Review evidence

- Reviewer/session: not started
- Findings: not started
- Resolution: not started
