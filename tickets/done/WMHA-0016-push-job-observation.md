---
id: WMHA-0016
title: Evaluate and add push-based job observation
status: done
type: research
priority: low
risk: high
created: 2026-08-01
updated: 2026-08-02
depends_on: [WMHA-0015]
---

# WMHA-0016: Evaluate and add push-based job observation

## Outcome

The project has measured evidence for whether SSE or webhook callbacks should supplement or replace polling, and implements the selected mechanism only when it improves reliability and cost without unsafe exposure.

## Why

Push updates may reduce latency and API traffic, but they introduce reconnect state, inbound reachability, authentication and lifecycle complexity.

## Required context

- `AGENTS.md`
- `docs/product/requirements.md`
- production observations from the stable polling implementation
- current Windmill SSE and webhook contracts

## Requirements

- Compare polling, SSE and webhook callbacks using measured API load, latency and failure recovery.
- Analyze Home Assistant restart, reconnect and network-boundary behavior.
- Require authenticated, replay-resistant callbacks if webhooks are selected.
- Preserve polling fallback unless evidence supports removal.

## Acceptance criteria

- [x] A source-backed comparison records benefits, costs and unresolved risks. — `docs/research/windmill-push-observation.md` (claim ledger with sources, 2026-08-02 verification dates, confidence levels; estimates labeled as code derivations).
- [x] The selected design has an accepted ADR. — `docs/architecture/decisions/0003-polling-remains-observation-mechanism.md`: polling remains the only mechanism; push deferred. Accepted; independent review done 2026-08-02.
- [x] Reconnect, duplicate, missed-event and restart scenarios are tested. — **Fulfilled through justified non-implementation; not applicable as literally written.** The ticket made implementation conditional on evidence; the evidence (no workspace-wide job stream, no signed outbound job webhook, no authenticated HA inbound channel) supports no push design, so there are no push scenarios to test. The polling path's equivalents are covered by the existing suite: duplicate/missed-event handling via watermark + seen-set (`tests/test_runs.py`), restart persistence (`tests/test_lifecycle.py`), backoff/reconnect of polling (`tests/test_health.py`, WMHA-0012). No push tests were added because no push code exists.
- [x] No public inbound endpoint is required without explicit user choice and security documentation. — Satisfied by the decision: no inbound endpoint was added or designed; the research note documents why every webhook design would have required one.
- [x] The stable polling path remains available when push is unsupported. — Polling is unchanged and remains the only mechanism (ADR-0003); no production code was touched.

## Decision record

Evidence-based outcome: **deferral**. Polling remains the only job-observation mechanism in v1.x.
Key facts (all in `docs/research/windmill-push-observation.md`):

1. Pinned Windmill v1.775.2 OpenAPI has only execution-scoped SSE (`getupdate_sse/{id}`, `run_and_stream`, plus `batch_rerun_jobs` streaming created UUIDs); no workspace-wide job lifecycle stream exists, so SSE cannot cover the `all`/`selected` run scopes.
2. Windmill's outbound workspace webhook emits resource lifecycle events only — no job events; job-completion notifications exist only as user-authored handler scripts (success handler EE-only).
3. HA webhooks are unauthenticated beyond a secret id and need inbound reachability (LAN, Nabu Casa cloud webhook, or public exposure) — the ticket's authenticated/replay-resistant requirement cannot be met and PR-015 forbids the dependency.
4. Code-derived polling cost: ≈ 2.5–3.7 bounded GETs/minute per fully enabled entry, ≤ 60 s detection latency. No production measurement exists; this evidence boundary is recorded in the research note and in `docs/product/supported-versions-and-limitations.md`.

Follow-up: `tickets/backlog/WMHA-0029-reevaluate-push-job-observation.md` owns the ADR-0003 revisit triggers.

## Non-goals

- Blocking the first stable release.
- Exposing arbitrary Windmill event payloads to Home Assistant.

## Validation evidence

| Check | Command or inspection | Result |
| --- | --- | --- |
| Repository guardrails | `python scripts/validate_repository.py` | pass, 2026-08-02 ("Repository validation passed (29 tickets checked)"); re-run after the review corrections, same result |
| Whitespace | `git diff --check` | pass, 2026-08-02 (also re-run after the review corrections) |
| Push-observation tests | project test command | not applicable — no push implementation (ADR-0003 deferral); the chosen mechanism is the existing polling path, validated by the 385-test suite that passed the WMHA-0015 quality gate on 2026-08-02 |

## Review evidence

- Reviewer/session: independent reviewer, 2026-08-02 — verdict "changes requested" (one mandatory correction; the deferral decision itself withstood review)
- Findings: 1 medium finding — the SSE inventory count in the research note and ADR validation was wrong (8 instead of 10 `text/event-stream` occurrences); the reviewer independently re-downloaded the pinned v1.775.2 `openapi.yaml` and identified the missed third family `POST /w/{workspace}/jobs/run/batch_rerun_jobs` (a batch re-run execution endpoint streaming created job UUIDs, not a job-observation stream). All other core claims (webhook event coverage, HA inbound model, polling cost derivation, AC honesty, ADR quality, WMHA-0029) were independently reproduced and accepted.
- Resolution: count re-verified against the raw pinned file (grep result: 10; `batch_rerun_jobs` at spec line 12808, `201` response "stream of created job uuids separated by \n"); `docs/research/windmill-push-observation.md` claim ledger corrected (three families, with `batch_rerun_jobs` explicitly classified as decision-irrelevant); ADR-0003 context and validation sections corrected and the correction itself re-verified. The core claim "no workspace-wide job lifecycle stream" is unchanged and confirmed by the reviewer's own count.
