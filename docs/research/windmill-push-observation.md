# Push-based job observation: polling vs. SSE vs. webhooks

Status: research baseline for WMHA-0016 and ADR-0003

Verified: 2026-08-02

Normative upstream baseline: Windmill `v1.775.2` (same pin as
`docs/research/windmill-api-contract.md`). Home Assistant side: webhook trigger documentation
(rolling source).

This note supplies the source-backed comparison required by WMHA-0016 AC 1: benefits, costs and
unresolved risks of supplementing or replacing the integration's bounded polling with SSE or
webhook callbacks. It does not decide; ADR-0003 decides.

## Evidence boundary (stated first)

WMHA-0016 names "production observations from the stable polling implementation" as required
context. **No such observations exist.** The v1 release evidence gap list in
`docs/product/supported-versions-and-limitations.md` records that no busy production workspace was
ever observed; polling bounds are client policy validated by tests and one disposable-instance
smoke, not by production load. Everything below labeled "estimate" is derived from the code's own
parameters, not measured in production. Nothing in this note is a production measurement.

## Sources

| Key | Primary source | Verified | Use |
| --- | --- | --- | --- |
| OAPI | [OpenAPI at v1.775.2](https://github.com/windmill-labs/windmill/blob/v1.775.2/backend/windmill-api/openapi.yaml) | 2026-08-02 (raw file grepped directly) | SSE endpoint existence, parameters, shapes |
| WEBHOOKS | [Windmill webhooks](https://www.windmill.dev/docs/core_concepts/webhooks) | 2026-08-02 | SSE stream webhooks, `getupdate_sse` event shape, workspace webhook event types |
| STREAMING | [Windmill streaming](https://www.windmill.dev/docs/core_concepts/streaming) | 2026-08-02 | streaming model overview |
| ERRORS | [Windmill error handling](https://www.windmill.dev/docs/core_concepts/error_handling) | 2026-08-02 | error/success handler contracts and edition gating |
| HA-WEBHOOK | [Home Assistant webhook trigger](https://www.home-assistant.io/integrations/webhook/) | 2026-08-02 | inbound reachability, authentication, `local_only` |
| CODE | `custom_components/windmill/coordinator.py`, `const.py` | 2026-08-02 | polling intervals, bounds, backoff, retention |

## Claim evidence ledger

| Claim | Direct evidence | Confidence | Implication | Ambiguity |
| --- | --- | --- | --- | --- |
| The SSE endpoints in v1.775.2 are all execution-scoped, none is a workspace-wide job lifecycle stream: per-job `GET /api/w/{workspace}/jobs_u/getupdate_sse/{id}` (1), the execute-and-stream family `POST\|GET /api/w/{workspace}/jobs/run_and_stream/{p,h,f,fv}/...` (8, GET+POST per variant), and `POST /api/w/{workspace}/jobs/run/batch_rerun_jobs` (1) | OAPI: 10 `text/event-stream` occurrences in the whole spec (verified by grep of the raw pinned file, 2026-08-02; an earlier count of 8 missed `batch_rerun_jobs` and was corrected after independent review) | High | No workspace-wide job lifecycle stream exists; SSE observation cannot cover the `all` or `selected` run scopes at all | None for the pinned release; later releases could add one (revisit trigger) |
| `batch_rerun_jobs` streams only the created job UUIDs of a batch re-run (`201`, "stream of created job uuids separated by \n") | OAPI lines for `/jobs/run/batch_rerun_jobs` | High | It is an execution response stream, not a job-update/observation stream — decision-irrelevant, listed only for inventory completeness | None |
| `getupdate_sse` streams log/result-stream/progress updates for one job id, with `running`, `log_offset`, `stream_offset`, `get_progress`, `only_result`, `no_logs`, `fast` query args | OAPI lines for `/jobs_u/getupdate_sse/{id}`; WEBHOOKS documents the event JSON (`type: update`, `new_result_stream`, `stream_offset`, completion event with `only_result`) | High | One long-lived connection per observed job; the stream's native payload includes result-stream/log classes the integration's denylist excludes | Exact scope requirement for restricted tokens unverified (likely `jobs:read` like other `jobs_u` GETs); stream lifetime/idle-timeout behavior undocumented |
| The workspace webhook (Windmill → external URL) emits only resource lifecycle events (script/flow/app/resource/resource-type/variable/folder CRUD) plus token-expiry events — **no job lifecycle events** | WEBHOOKS: "Workspace webhook" event-type table | High | No outbound platform webhook can report job completion; webhook-based run observation has no contract to build on | Signature/secret support: the page documents none (a URL field only); absence of a feature in docs is medium confidence, but no signed contract was found anywhere |
| The instance events webhook is EE-only and covers user lifecycle events, not jobs | WEBHOOKS: "Instance events webhook" | High | Irrelevant to job observation | None |
| Outbound job notifications exist only as user-authored handlers: workspace error handler (custom script/flow receives `job_id`, `path`, `is_flow`, `started_at`, `email`, …) and workspace success handler (**Enterprise Edition only**) | ERRORS: "Workspace error handler", "Workspace success handler" | High | On CE there is no success-completion hook at all; on EE it is a user-maintained script, not a platform contract with signatures, retries or replay protection | Exact edition availability of the *custom* workspace error handler is not stated unambiguously (Slack/Teams entries are edition-tagged; custom is not) — recorded as ambiguity, decision does not depend on it |
| HA webhook triggers are unauthenticated beyond the secret `webhook_id`; default `local_only: true` allows same-network callers or Nabu Casa Cloud webhooks; internet exposure requires an explicit user opt-out | HA-WEBHOOK: "Webhook security" section | High | Inbound push from Windmill requires (a) same-LAN deployment, (b) a Nabu Casa cloud webhook, or (c) the user exposing HA to the internet — there is no authenticated, replay-resistant HA inbound channel to match the ticket's webhook requirement | Cloud webhook availability depends on the user's subscription — deployment fact, not code |

## Polling baseline (derived from code, labeled as derivation)

Per config entry, steady state, all features enabled:

| Coordinator | Interval | Requests per cycle (typical → worst) | Requests/day (typical → worst) |
| --- | --- | --- | --- |
| Runs | 60 s | 1 → 3 pages (`MAX_RUN_PAGES`, early stop at watermark/short page) | 1,440 → 4,320 |
| Health | 60 s | 1 → 2 (coarse + optional detailed) | 1,440 → 2,880 |
| Workers (opt-in) | 120 s | 1 → 5 pages | 720 → 3,600 |
| Runnables | 30 min | 1 per selection (≤25) | ≤ 1,200 (typical: a handful) |
| Capabilities | 6 h | fixed small probe set | ≈ 16 |
| Update | 6 h | 1 | 4 |

Typical fully-enabled entry: ≈ 3,700–5,300 requests/day ≈ **2.5–3.7 requests/minute**, all
bounded GETs with explicit page sizes. No normative global Windmill rate limit exists in the
pinned sources; on 429 the coordinator stretches to 300–900 s. These are derivations from
`coordinator.py`/`const.py`, not production measurements.

Detection latency: a completion is observed at the next run poll → worst case ≈ 60 s, mean ≈ 30 s.
Documented restart behavior: watermark + bounded seen-set persisted; one-poll startup loss window
(accepted limitation 2, WMHA-0022/WMHA-0023).

## Comparison

| Dimension | Polling (status quo) | Per-job SSE (`getupdate_sse` / `run_and_stream`) | Webhook callbacks |
| --- | --- | --- | --- |
| Contract coverage | Workspace-wide listing covers all three run scopes | **Per single job only** — cannot observe `all` or `selected` scopes; only HA-started jobs have an id to attach to | **No job-completion contract exists** (CE: none; EE: user-authored success/error handler scripts) |
| API load (estimate) | ~2.5–3.7 req/min per entry, bounded | Near-zero requests while connected, but one long-lived connection per tracked job (registry holds up to 50) | Near-zero |
| Latency | ≤ 60 s (mean ~30 s) | Near-real-time for the attached job | Near-real-time where a handler exists |
| Failure recovery | Stateless recovery: next poll re-reads a time window; watermark + seen-set make duplicates impossible; missed events bounded by the window | Disconnect/restart loses stream state; `log_offset`/`stream_offset` resume state would need persistence; a completion during a gap is invisible → **polling must remain as the fallback anyway** | Delivery is at-most-once with no documented retry; a missed callback is invisible → **polling must remain as the fallback anyway** |
| HA restart/reconnect | Survives trivially; state reloaded from stores | Every HA restart drops all streams; reconnect lifecycle adds a second failure domain on top of polling | Callbacks arriving while HA is down are lost |
| Network boundary | Outbound only; works behind NAT, with Cloud and self-hosted | Outbound only (HA initiates); long-lived connection through proxies is a new operational risk | **Inbound to HA required**: same LAN, Nabu Casa cloud webhook, or public exposure of HA (`local_only: false`) — contradicts PR-015's rule that v1 must not depend on inbound public reachability |
| Auth / replay resistance | Bearer header, least-privilege `jobs:read` | Bearer header, same token | HA webhook: unauthenticated beyond secret id; Windmill workspace webhook: no signature/secret documented; handler scripts: no signing at all. **The ticket's "authenticated, replay-resistant callbacks" requirement cannot be met** |
| Sensitive data exposure | Bounded allowlist parsing | Stream natively carries result-stream/log classes on the integration's denylist; would need strict `no_logs`/allowlist filtering of an untrusted stream | Handler payloads include `email` and other denylisted fields; payload arrives inbound and must be treated as hostile |
| Cost of ownership | Exists, 385-test suite, released quality gate passed | New reconnect/state machine + persistence + denylist filtering of a streaming payload, in addition to unchanged polling | New inbound endpoint, reachability setup UX, security documentation, in addition to unchanged polling |

## Benefits, costs, unresolved risks

Benefits of push that the evidence supports: lower completion-detection latency for
**HA-started jobs only** (SSE), and marginally lower request volume. Both are real but small at
the current poll cadence.

Costs that the evidence supports: SSE cannot replace polling for the `all`/`selected` scopes (no
workspace feed exists), so it can only add a second observation path with its own reconnect,
restart, resume-state and payload-filtering machinery. Webhooks have no job-completion contract on
any edition the integration supports, cannot satisfy the ticket's auth/replay requirement, and
require inbound reachability that PR-015 forbids as a v1 dependency.

Unresolved risks if push were built anyway:

1. Stream resume semantics (`log_offset`/`stream_offset`) across reconnects are undocumented —
   duplicate/missed-event behavior would have to be reverse-engineered and pinned by version.
2. Idle timeouts and proxy behavior for hour-long SSE connections are unknown; HA runs behind
   arbitrary home proxies.
3. Restricted-token scope for `getupdate_sse` is unverified (likely `jobs:read`, unproven).
4. Any inbound webhook path inherits HA's unauthenticated webhook model; replay resistance would
   have to be built application-side with no upstream signature to verify against.

## Re-evaluation triggers (input to the ADR's "revisit when")

- Upstream adds a workspace-wide job lifecycle event stream or signed outbound job webhooks
  (check the release notes/OpenAPI of the pinned-version successor).
- Production observations (WMHA-0026's live-traffic check or user reports) show the 60 s cadence
  is a real latency or load problem.
- Home Assistant gains an authenticated inbound webhook primitive beyond secret-id URLs.

## Successor check 2026-08-02 (WMHA-0029)

Re-check of the ADR-0003 revisit conditions against the successor release line. At check time the
only release after the pinned v1.775.2 is **v1.776.0** (published 2026-08-01; GitHub Releases API,
`repos/windmill-labs/windmill/releases`, queried 2026-08-02). This matches the live `/api/uptodate`
observation from the WMHA-0015 smoke (installed v1.775.2 → latest v1.776.0).

New sources for this delta:

| Key | Primary source | Verified | Use |
| --- | --- | --- | --- |
| REL-1776 | [Windmill v1.776.0 release](https://github.com/windmill-labs/windmill/releases/tag/v1.776.0) | 2026-08-02 (release notes read in full) | successor changelog spot check |
| OAPI-1776 | [OpenAPI at v1.776.0](https://github.com/windmill-labs/windmill/blob/v1.776.0/backend/windmill-api/openapi.yaml) | 2026-08-02 (raw file grepped directly) | SSE inventory, webhook/signature search, path diff vs v1.775.2 |
| GH-REL | [GitHub Releases API](https://api.github.com/repos/windmill-labs/windmill/releases) | 2026-08-02 | complete successor release set |

Findings per revisit condition:

1. **Workspace-wide job lifecycle stream — not present.** The raw v1.776.0 `openapi.yaml`
   contains exactly **10 `text/event-stream` occurrences**, the same count and the same three
   execution-scoped path families as the v1.775.2 baseline: 8 in the `run_and_stream` family
   (GET+POST for `f/{path}`, `fv/{version}`, `p/{path}`, `h/{hash}`), 1 in
   `POST /api/w/{workspace}/jobs/run/batch_rerun_jobs`, 1 in
   `GET /api/w/{workspace}/jobs_u/getupdate_sse/{id}`. A full path diff of the two pinned specs
   shows only these additions: dbt runtime endpoints (`/dbt/*`, `jobs/dbt_graph/{id}`,
   `jobs/dbt_resumable*`), per-job `GET /api/w/{workspace}/jobs/run_progress/{id}` (polled
   `application/json` per-relation progress for one job id — a polling endpoint, not a stream,
   and per-job/execution-scoped), `workspaces/seed_full_diff`, and
   `settings/github_app_stale_webhooks` (inbound git-sync housekeeping). One removal:
   `workspaces/edit_deploy_to`. No workspace-wide job event stream exists in v1.776.0.
2. **Signed outbound job webhooks — not present.** `POST /api/w/{workspace}/workspaces/edit_webhook`
   is unchanged and still takes a bare `{ "webhook": "<url>" }` string with no secret or signature
   field. The rolling webhooks documentation (re-fetched 2026-08-02) still lists only resource
   lifecycle and token-expiry event types for the workspace webhook — no job events — and documents
   no payload signing. HMAC mentions in the v1.776.0 spec are pre-existing unrelated mechanisms
   (job resume/cancel approval signatures, the per-job `job_view_token` present identically in
   v1.775.2, EE telemetry, S3 presigned objects); `webhook_secret` belongs to inbound git-sync
   auto-pull settings. The v1.776.0 release notes contain no job event stream or outbound job
   webhook feature (the "dedicated base url for GitHub webhook delivery" feature is inbound
   git-sync plumbing; "stamp webhook trigger_kind on token-driven job runs" is job metadata).
3. **Authenticated HA inbound primitive — not present (unchanged).** The Home Assistant webhook
   trigger documentation (re-fetched 2026-08-02) still states webhook endpoints "don't require
   authentication, other than knowing a valid webhook ID", with `local_only` as the reachability
   gate. No authenticated, replay-resistant inbound webhook primitive exists.
4. **Production evidence — still absent (evidence boundary unchanged).** WMHA-0026 remains in the
   backlog; no live-traffic observation and no user reports about the 60 s latency or request
   volume exist. The WMHA-0015 smoke remains the only live observation and reported no latency or
   load problem.
5. **Windmill Cloud tenant-safe push channel — not found** in the successor OpenAPI, release
   notes, or the re-fetched rolling documentation.

Outcome: **no revisit condition fired; ADR-0003 is re-confirmed with verification date
2026-08-02.** The next check is due at the next Windmill pin bump or when WMHA-0026 produces
live-traffic evidence.
