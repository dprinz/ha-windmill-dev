# ADR-0003: Polling remains the only job-observation mechanism; push is deferred

- Status: accepted
- Date: 2026-08-02
- Deciders: project owner through WMHA-0016, independent review done 2026-08-02
- Related tickets: WMHA-0016, WMHA-0007, WMHA-0026, follow-up WMHA-0029
- Supersedes: none

## Context

The integration observes Windmill job activity exclusively through bounded polling
(`WindmillRunCoordinator`: 60 s interval, ≤3 pages × 100, watermark + bounded seen-set
persistence). WMHA-0016 required an evidence-based decision on whether SSE or webhook callbacks
should supplement or replace polling, and PR-015 forbids making the first stable release depend on
inbound public reachability from Windmill to Home Assistant.

The primary-source check on 2026-08-02 (`docs/research/windmill-push-observation.md`) established:

1. The pinned v1.775.2 OpenAPI contains **no workspace-wide job lifecycle stream**. All 10
   `text/event-stream` occurrences are execution-scoped: per-job
   `GET /api/w/{workspace}/jobs_u/getupdate_sse/{id}`, the execute-and-stream `run_and_stream`
   family, and `POST /api/w/{workspace}/jobs/run/batch_rerun_jobs` (streams only the created job
   UUIDs of a batch re-run — an execution response, not an observation stream).
2. Windmill's outbound workspace webhook emits resource lifecycle and token events only — **no job
   events**. Job-completion notifications exist only as user-authored handler scripts, and the
   success handler is Enterprise Edition only.
3. Home Assistant webhook triggers are unauthenticated beyond a secret URL id; inbound delivery
   requires same-LAN deployment, a Nabu Casa cloud webhook, or exposing HA to the internet.

Polling cost derived from the code is ≈ 2.5–3.7 bounded GET requests/minute per fully enabled
config entry, with ≤ 60 s completion-detection latency. No production-traffic measurement exists;
this is an explicitly recorded evidence boundary, not a hidden assumption.

## Decision drivers

- No workspace-wide job stream exists, so SSE can never observe the `all` or `selected` run scopes
  and could only ever cover HA-started jobs — polling would remain mandatory regardless.
- The ticket mandates authenticated, replay-resistant callbacks if webhooks are selected; no such
  contract exists on either the Windmill or the Home Assistant side.
- PR-015 forbids an inbound-reachability dependency; every webhook design requires one.
- Push would add a second observation path (reconnect state, resume offsets, stream payload
  filtering against the sensitive-data denylist, inbound endpoint security) while removing
  nothing.
- Polling already survives HA restarts and network gaps with persisted, deduplicated state.

## Considered options

1. Replace polling with per-job SSE for HA-started jobs.
2. Supplement polling with per-job SSE for HA-started jobs (hybrid).
3. Webhook callbacks via a user-configured Windmill handler script posting to an HA webhook.
4. Keep polling as the only mechanism; re-evaluate when the upstream contract or measured load
   changes. Chosen.

## Decision

Bounded polling remains the **only** job-observation mechanism in v1.x. No SSE client, no inbound
webhook endpoint and no push-related configuration is added. Push-based observation is re-evaluated
only when one of the revisit conditions below is met; the follow-up ticket WMHA-0029 owns that
re-check.

This decision satisfies the WMHA-0016 acceptance criteria through a justified non-implementation:
there is no push design to test (AC 3 is not applicable), no inbound endpoint is required (AC 4),
and the polling path is untouched (AC 5). The ticket explicitly made implementation conditional on
evidence; the evidence supports deferral.

## Consequences

### Positive

- One observation path, one failure domain, one tested recovery model (watermark + seen-set).
- Zero inbound attack surface; no reachability setup, no security documentation debt.
- Completion observation works identically for Windmill Cloud, CE and EE, behind NAT, without a
  Home Assistant Cloud subscription.
- The denylist is enforced on bounded, allowlist-parsed responses — not on a hostile inbound
  stream.

### Negative

- Completion-detection latency stays at up to one poll interval (mean ≈ 30 s, worst ≈ 60 s).
- Request volume stays at ≈ 2.5–3.7 requests/minute per entry instead of near-zero.
- HA-started long jobs cannot report progress; only completion is observable (unchanged).

### Risks and mitigations

- Real deployments may find the 60 s latency or request volume problematic — WMHA-0026 includes a
  bounded live-traffic observation; user feedback after release feeds the revisit triggers.
- Upstream may add a workspace-wide event stream in a later release — WMHA-0029 re-checks the
  pinned-version successor contract; `docs/research/source-register.md` dates every claim.
- "Deferred" quietly becoming "forgotten" — the revisit triggers are concrete and owned by a
  backlog ticket, not by memory.

## Validation

- `docs/research/windmill-push-observation.md` records the claim ledger: every material claim has
  a primary source, a 2026-08-02 verification date and a confidence level; estimates are labeled
  as code derivations.
- The SSE endpoint inventory was verified by grepping the raw pinned `openapi.yaml` at v1.775.2
  (10 `text/event-stream` occurrences, all execution-scoped; an initial count of 8 missed
  `batch_rerun_jobs` and was corrected after independent review, with the correction re-verified
  against the raw file).
- No production code changed; the existing 385-test suite and its restart/dedup/persistence
  coverage remain the validation of the chosen mechanism.
- Decision remains sound while: no workspace-wide job stream appears in a successor OpenAPI, HA
  has no authenticated inbound webhook primitive, and no measured evidence shows polling latency
  or load is a real problem.

## Revisit when

- A Windmill release adds a workspace-wide job lifecycle event stream or signed outbound job
  webhooks (detectable in its OpenAPI/changelog).
- WMHA-0026's live-traffic observation or user reports show the 60 s cadence causes real latency
  or load problems.
- Home Assistant introduces an authenticated, replay-resistant inbound webhook primitive.
- Windmill Cloud documents a tenant-safe push channel.
