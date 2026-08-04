# Windmill API contract for the Home Assistant integration

Status: verified research baseline for WMHA-0001

Verified: 2026-08-01

Normative upstream baseline: Windmill `v1.775.2` (released 2026-07-29)

This document is the implementation contract for the first Home Assistant release. It
distinguishes facts in the pinned OpenAPI/source from client policy and from behavior that
must still be capability-probed. A missing optional endpoint or permission must disable only
that feature; it must not invalidate an otherwise usable config entry.

## Sources and evidence levels

| Key | Primary source | Use |
| --- | --- | --- |
| OAPI | [OpenAPI at v1.775.2](https://github.com/windmill-labs/windmill/blob/v1.775.2/backend/windmill-api/openapi.yaml) | Methods, paths, parameters and response schemas |
| API-SRC | [API router at v1.775.2](https://github.com/windmill-labs/windmill/blob/v1.775.2/backend/windmill-api/src/lib.rs) | Route layering and version/update implementation |
| HEALTH-SRC | [Health implementation at v1.775.2](https://github.com/windmill-labs/windmill/blob/v1.775.2/backend/windmill-api/src/health.rs) | Cache, status calculation and authorization behavior |
| RELEASE | [Windmill v1.775.2 release](https://github.com/windmill-labs/windmill/releases/tag/v1.775.2) | Pinned release and verification target |
| TOKENS | [User tokens](https://www.windmill.dev/docs/core_concepts/user_tokens) | Bearer authentication and granular scope syntax |
| WEBHOOKS | [Webhooks](https://www.windmill.dev/docs/core_concepts/webhooks) | Async execution and job identifiers |
| JOBS | [Jobs](https://www.windmill.dev/docs/core_concepts/jobs) | Job lifecycle semantics |
| VERSIONING | [Versioning](https://www.windmill.dev/docs/core_concepts/versioning) | Script hashes and flow versions |
| SELF-HOST | [Self-host documentation](https://www.windmill.dev/docs/advanced/self_host) | Health checks and deployment context |
| WORKERS | [Worker groups](https://www.windmill.dev/docs/core_concepts/worker_groups) | Worker-group edition behavior |
| SCOPES-SRC | [Scope middleware at v1.775.2](https://github.com/windmill-labs/windmill/blob/v1.775.2/backend/windmill-api-auth/src/scopes.rs) | Route-domain and HTTP-action scope enforcement |
| WORKERS-SRC | [Worker handlers at v1.775.2](https://github.com/windmill-labs/windmill/blob/v1.775.2/backend/windmill-api-workers/src/lib.rs) | Worker visibility and DevOps-role enforcement |
| CONFIGS-SRC | [Config handlers at v1.775.2](https://github.com/windmill-labs/windmill/blob/v1.775.2/backend/windmill-api-configs/src/lib.rs) | Worker-group access and config obfuscation |
| AUTH-SRC | [Authentication extractor at v1.775.2](https://github.com/windmill-labs/windmill/blob/v1.775.2/backend/windmill-api-auth/src/auth.rs) | Application of route scopes to scoped tokens |

`OAPI`, `API-SRC` and `HEALTH-SRC` are pinned to an immutable release. The documentation
pages are rolling sources and must be rechecked when the client compatibility floor changes.

Evidence terms used below:

- **verified**: explicit in the pinned OpenAPI or source;
- **inference**: follows from multiple primary-source facts but is not an upstream promise;
- **probe**: authorization, edition or deployment behavior must be detected at runtime;
- **policy**: behavior chosen for this integration rather than guaranteed by Windmill.

### Claim evidence ledger

This ledger supplies direct evidence for each material contract family. Endpoint tables later in
the document use the same contract and evidence terms.

| Claim | Direct evidence | Confidence | Implementation implication | Ambiguity |
| --- | --- | --- | --- | --- |
| Version is public in v1.775.2; health status is public and detailed health is authenticated | [public router lines 952–968](https://github.com/windmill-labs/windmill/blob/v1.775.2/backend/windmill-api/src/lib.rs#L952-L968), [health OpenAPI lines 44–100](https://github.com/windmill-labs/windmill/blob/v1.775.2/backend/windmill-api/openapi.yaml#L44-L100) | High | Use version only for reachability; authenticate detailed health | OpenAPI's global security declaration conflicts with the public source route for version |
| `whoami` is a users-domain GET and restricted tokens need `users:read` | [whoami path lines 2661–2678](https://github.com/windmill-labs/windmill/blob/v1.775.2/backend/windmill-api/openapi.yaml#L2661-L2678), [scope domains/actions lines 361–455](https://github.com/windmill-labs/windmill/blob/v1.775.2/backend/windmill-api-auth/src/scopes.rs#L361-L455), [route check lines 457–553](https://github.com/windmill-labs/windmill/blob/v1.775.2/backend/windmill-api-auth/src/scopes.rs#L457-L553) | High | Recommend `users:read`; add `workspaces:read` only for workspace listing/name | Handler-level user visibility still applies in addition to scope middleware |
| Workspace name is plain text | [OpenAPI lines 3288–3302](https://github.com/windmill-labs/windmill/blob/v1.775.2/backend/windmill-api/openapi.yaml#L3288-L3302) | High | Parse bounded text, not JSON | None for pinned release |
| Health models, cache and worker liveness are bounded | [health schemas lines 24530–24699](https://github.com/windmill-labs/windmill/blob/v1.775.2/backend/windmill-api/openapi.yaml#L24530-L24699), [health implementation](https://github.com/windmill-labs/windmill/blob/v1.775.2/backend/windmill-api/src/health.rs#L1-L601), [scoped-token check lines 769–784](https://github.com/windmill-labs/windmill/blob/v1.775.2/backend/windmill-api-auth/src/auth.rs#L769-L784), [scope domains lines 361–415](https://github.com/windmill-labs/windmill/blob/v1.775.2/backend/windmill-api-auth/src/scopes.rs#L361-L415) | High | Prefer aggregate health over individual-worker data | Docs say superadmin for detailed health while pinned handler accepts `ApiAuthed`; v1.775.2 scoped-token middleware has no `health` domain, so effectively unscoped tokens only |
| Worker list is authenticated with visibility redaction; queue aggregates require DevOps | [worker list lines 100–143](https://github.com/windmill-labs/windmill/blob/v1.775.2/backend/windmill-api-workers/src/lib.rs#L100-L143), [queue handlers lines 267–307](https://github.com/windmill-labs/windmill/blob/v1.775.2/backend/windmill-api-workers/src/lib.rs#L267-L307) | High | Treat empty worker list as potentially policy-hidden; require DevOps for queue endpoints | Environment flags can hide workers/tags from non-DevOps users |
| Worker-group listing needs authentication and obfuscates static env values for non-admins | [config handler lines 62–105](https://github.com/windmill-labs/windmill/blob/v1.775.2/backend/windmill-api-configs/src/lib.rs#L62-L105) | High | Discard config and retain group name only | Other arbitrary config fields are not proven safe even after upstream obfuscation |
| Pagination is page-based, defaults to 30 and caps at 100 | [common parameters lines 24043–24055](https://github.com/windmill-labs/windmill/blob/v1.775.2/backend/windmill-api/openapi.yaml#L24043-L24055) | High | Send explicit bounded values and overlap polling windows | Stable snapshot/cursor semantics are not promised |
| Job union and required fields use UUID identifiers | [queued/completed schemas lines 25646–25906](https://github.com/windmill-labs/windmill/blob/v1.775.2/backend/windmill-api/openapi.yaml#L25646-L25906), [union lines 26217–26234](https://github.com/windmill-labs/windmill/blob/v1.775.2/backend/windmill-api/openapi.yaml#L26217-L26234) | High | Deduplicate by UUID and parse an allowlist | Many response fields are optional and sensitive |
| Job listing/get/result/cancel contracts exist at the recorded paths | [list/get paths lines 13356–14960](https://github.com/windmill-labs/windmill/blob/v1.775.2/backend/windmill-api/openapi.yaml#L13356-L14960) | High | Use metadata reads; never poll arbitrary result; cancel only tracked IDs | Error bodies are not normatively modeled |
| Normal restricted-token cancellation needs `jobs:write` plus per-job authorization | [POST-to-write and jobs-domain mapping](https://github.com/windmill-labs/windmill/blob/v1.775.2/backend/windmill-api-auth/src/scopes.rs#L361-L364), [method mapping lines 586–598](https://github.com/windmill-labs/windmill/blob/v1.775.2/backend/windmill-api-auth/src/scopes.rs#L586-L598), [handler authorization lines 526–540](https://github.com/windmill-labs/windmill/blob/v1.775.2/backend/windmill-api/src/jobs.rs#L526-L540) | High | Request `jobs:write`; still cancel only eligible tracked jobs | App-embed sentinel exception is irrelevant to this integration |
| Script/flow latest and pinned execution returns asynchronous job IDs | [script paths lines 8590–9975](https://github.com/windmill-labs/windmill/blob/v1.775.2/backend/windmill-api/openapi.yaml#L8590-L9975), [flow/run paths lines 10680–13000](https://github.com/windmill-labs/windmill/blob/v1.775.2/backend/windmill-api/openapi.yaml#L10680-L13000) | High | Persist addressing mode and validate returned UUID | Exact resource matching for restricted hash/version execution needs an instance test |
| `/uptodate` is a GitHub-backed best-effort plain-text contract | [route lines 962–966](https://github.com/windmill-labs/windmill/blob/v1.775.2/backend/windmill-api/src/lib.rs#L962-L966), [implementation lines 1138–1168](https://github.com/windmill-labs/windmill/blob/v1.775.2/backend/windmill-api/src/lib.rs#L1138-L1168) | High for pinned source | Map failures/unparseable text to update `unknown` | GitHub availability and output format are external dependencies |

## Base URL, authentication and setup

All paths below are relative to a normalized base URL and the OpenAPI server prefix `/api`.
The client must reject base URLs containing user-info, strip a trailing slash, preserve an
explicit deployment path, require `https` except for loopback/test deployments, and send the
token only as `Authorization: Bearer <token>`. Windmill also supports token query parameters
for some webhooks, but this integration must never use them. [OAPI, TOKENS, WEBHOOKS]

| Purpose | Contract | Authentication | Success model | Client use |
| --- | --- | --- | --- | --- |
| Reachability/version | `GET /api/version` | Public in the pinned v1.775.2 router; OpenAPI's inherited bearer declaration is contradictory | `200 text/plain`, source formats `CE <version>` or `EE <version>` | Reachability and version hint only; never authentication proof |
| Visible workspaces | `GET /api/workspaces/list` | Bearer | `200 application/json`, array of visible `Workspace` objects | Optional workspace chooser |
| Token/workspace validation | `GET /api/w/{workspace}/users/whoami` | Bearer plus workspace access | `200 User`; includes `username`, role booleans and membership metadata | Canonical validation call; retain only bounded identity/role facts in memory |
| Workspace display name | `GET /api/w/{workspace}/workspaces/get_workspace_name` | Bearer plus workspace access | `200 text/plain`, string | Optional label lookup after `whoami` |

Setup classification is a client policy:

| Observation | Config-flow result |
| --- | --- |
| DNS, connect, TLS or bounded request timeout | `cannot_connect` |
| HTTP `401` | `invalid_auth` |
| HTTP `403` from `whoami` | `insufficient_permission` |
| HTTP `404` from workspace-scoped validation after `/version` succeeds | `invalid_workspace` (the deployment may also be too old; include that in diagnostics) |
| Successful response with an invalid content type or model | `unexpected_response` |
| Other `5xx` | `server_error`, retryable |

The stable, non-secret config-entry identity is the normalized origin/deployment path plus
workspace ID. It deliberately excludes the token and mutable workspace display name.

## Version, edition and capability negotiation

| Capability | Contract | Model and interpretation | Availability |
| --- | --- | --- | --- |
| Installed version/edition | `GET /api/version` | Public `200 text/plain` with `CE <version>` or `EE <version>` in pinned source; parse defensively and retain the raw bounded value for diagnostics | Shared endpoint in v1.775.2; capability-probe only for older compatibility targets |
| Coarse health | `GET /api/health/status?force=false` | `200` healthy/degraded or `503` unhealthy; `HealthStatusResponse` has `status`, `checked_at`, `database_healthy`, `workers_alive`; cached for five seconds unless forced | No auth (`security: []`); introduced after older releases, so `404` means unsupported |
| Detailed health | `GET /api/health/detailed` | `200` or `503`; always-fresh `DetailedHealthResponse` described below | Authenticated in OAPI. The v1.775.2 handler accepts `ApiAuthed`, but granular-scoped tokens fail earlier because the scope middleware has no `health` domain; probe only as optional with an effectively unscoped token and never require a broader token for core features |
| Up-to-date check | `GET /api/uptodate` | Plain text exactly `yes`, or `Update: <installed> -> <latest>`; pinned source makes an outbound GitHub latest-release call with a ten-second timeout | Self-host only in product policy; fragile external dependency, so failure yields `unknown` rather than entry failure |
| License string | `GET /api/ee_license` | Plain text, empty for CE/no valid license; a non-empty license identifier is sensitive | Do not call: `/version` is sufficient for edition and avoids collecting license data |

Capability discovery must be explicit and cached per config-entry refresh cycle. The client
records `available`, `unauthorized`, `unsupported`, `temporarily_unavailable`, or `not_applicable`
for each optional feature. `401` invalidates authentication; `403` means unauthorized; `404`
means unsupported only for an endpoint-level probe (not for a user-selected resource); network
and `5xx` failures are temporary. No feature is inferred from edition alone when it can be
probed safely. [OAPI, API-SRC, HEALTH-SRC]

## Health, database, queue and workers

`GET /api/health/detailed` returns:

- overall `status`, `checked_at`, and `version`;
- `checks.database`: `healthy`, `latency_ms`, and pool `size`, `idle`, `max_connections`;
- nullable `checks.workers`: `healthy`, `active_count`, `worker_groups`, `min_version`, and
  observed `versions`;
- nullable `checks.queue`: `pending_jobs` and `running_jobs`;
- `checks.readiness`.

The pinned source defines an alive worker as one that pinged within the previous five minutes.
If the database cannot be queried, worker and queue checks may be null. These bounded aggregate
fields are the preferred PR-004/PR-005 source. [OAPI, HEALTH-SRC]

Administrative fallbacks are optional:

| Endpoint | Response | Minimum access contract | Handling |
| --- | --- | --- | --- |
| `GET /api/workers/list?page=1&per_page=N&ping_since=300` | `WorkerPing[]` | Authenticated and `workers:read` for restricted tokens; no DevOps role is required, but `HIDE_WORKERS_FOR_NON_ADMINS` may yield an empty list and non-DevOps responses hide last-job IDs plus possibly custom tags | Disabled by default; never expose `ip`, last job/workspace IDs, or individual workers without opt-in |
| `GET /api/workers/queue_counts` | map of tag to queued count | Authenticated, restricted-token `workers:read`, and DevOps role | Optional aggregate queue pressure |
| `GET /api/workers/queue_running_counts` | map of tag to running count | Authenticated, restricted-token `workers:read`, and DevOps role | Optional aggregate running pressure |
| `GET /api/workers/queue_metrics` | time-series arrays | Authenticated, restricted-token `workers:read`, and DevOps role in v1.775.2 | Not required for v1; prefer bounded current counts |
| `GET /api/configs/list_worker_groups` | array `{name, config}` | Authenticated and `configs:read` for restricted tokens; no admin role required, but static env values are obfuscated for non-admins | Read names only; arbitrary `config` can contain sensitive deployment data and must be discarded |

The detailed-health aggregates are required only when authorized. Worker lists, group config and
metrics are administrative enhancements. A normal workspace token must still load execution and
job features when every administrative probe returns `403` or `404`.

## Jobs and run observation

All job APIs use UUID job IDs. `Job` is a discriminated union of `QueuedJob` and `CompletedJob`.
The schemas include sensitive fields, so the client must parse only an allowlist.

| Purpose | Contract | Important filters/model |
| --- | --- | --- |
| Unified bounded listing | `GET /api/w/{workspace}/jobs/list` | `Job[]`; request `has_null_parent=true`, `is_flow_step=false`, bounded `per_page`, time/status/path filters as needed |
| Queue listing | `GET /api/w/{workspace}/jobs/queue/list` | `QueuedJob[]`; supports `page`, `per_page`, `running`, parent/path/hash/date/kind/suspended filters |
| Completed listing | `GET /api/w/{workspace}/jobs/completed/list` | `CompletedJob[]`; supports status (`success`, `failure`, `canceled`, `skipped`), top-level/flow-step, date/path and pagination filters |
| One job | `GET /api/w/{workspace}/jobs_u/get/{id}?no_logs=true&no_code=true` | `Job`; always suppress logs and code |
| Completed metadata | `GET /api/w/{workspace}/jobs_u/completed/get/{id}` | `CompletedJob`; parse allowlist only |
| Arbitrary result | `GET /api/w/{workspace}/jobs_u/completed/get_result/{id}` | Arbitrary JSON | Not polled or stored; a later action may return a strictly bounded, redacted subset |
| Cancel | `POST /api/w/{workspace}/jobs_u/queue/cancel/{id}` with JSON `{ "reason": "Canceled from Home Assistant" }` | `200 text/plain`; `401/403/404` must remain distinct | Only IDs in the bounded Home Assistant-started registry; no approval token query parameter |

Common pagination starts at page 1, defaults to 30 and allows at most 100 items per page. The
integration must always send explicit page/per-page values. Polling uses a descending time window
with deliberate overlap, deduplicates by job UUID, advances its watermark only after a complete
successful page sequence, and caps pages, observed IDs and retained Home Assistant-started jobs.
This is client policy designed to tolerate concurrent inserts without unbounded scans. [OAPI]

### `jobs/list` pagination is only half a page (verified 2026-08-04)

`per_page` on `GET /api/w/{workspace}/jobs/list` is **not a row count**. The handler builds
`queue UNION ALL completed`. Only the completed subquery receives `per_page`; the queued
subquery is built with `Pagination { per_page: None, page: None }`, which
`paginate_without_limits` resolves to `MAX_PER_PAGE = 10000`, and the union carries no outer
`LIMIT`. A request with `per_page=N` therefore answers with up to N completed rows **plus
every queued and running top-level job**. The union is not globally ordered either — queued
rows precede completed rows — so a client must never truncate a page to a bound.

The same handler ignores `offset`: it logs "offset is not 0, but is ignored for list_jobs" and
hardcodes `offset 0` for the completed half, so page 2 of a walk repeats page 1. Clients must
deduplicate by job UUID before aggregating. Setting `created_before`, `completed_before`,
`started_before`, `success`, `status`, `label`, `result` or `is_skipped` switches the handler
to a completed-only query that *is* bounded by `per_page` — at the price of losing the queued
half, and with it the running/queued counts.

Sources, pinned at the `v1.768.0` of the reporting instance:
[`list_jobs` L2949-L3043](https://github.com/windmill-labs/windmill/blob/v1.768.0/backend/windmill-api/src/jobs.rs#L2949-L3043),
[`list_queue_jobs_query` L252-L265](https://github.com/windmill-labs/windmill/blob/v1.768.0/backend/windmill-api-jobs/src/query.rs#L252-L265),
[`paginate_without_limits` L297-L311](https://github.com/windmill-labs/windmill/blob/v1.768.0/backend/windmill-common/src/utils.rs#L297-L311).
The same shape is present at the pinned baseline `v1.775.2`. Confidence: high (primary
source), corroborated by a live report: a CE `v1.768.0` instance with one running job made the
`per_page=1` capability probe report `runs: unsupported / unexpected_response` and disabled
run observation (WMHA-0038). The `jobs/list` probe failure recorded on 2026-08-02 as a
workspace-propagation race is at least partly explained by this instead.

Consequence for the client: the row bound for every `jobs/list` read is a client-side maximum
(`MAX_JOB_ROWS`), never the requested page size, and the transport's `MAX_RESPONSE_BYTES`
stays the outer guarantee. A page is short when its *completed* rows are fewer than
`per_page`.

Safe job fields are `id`, union type/state, `parent_job`, `created_at`, `started_at`,
`completed_at`, `duration_ms`, `success`, `canceled`, `script_path`, `script_hash`, `job_kind`,
and `is_flow_step`. Discard free-form `tag` and label values by default; a later feature may map
an explicitly configured allowlist to internal identifiers. Never retain or expose `args`, `result`, `logs`,
`raw_code`, `raw_flow`, `flow_status`, `email`, `permissioned_as`, cancellation free text,
worker/IP identifiers or arbitrary error/stack content.

## Runnable discovery, addressing and execution

| Kind | Discover/list | Read metadata | Async execute | Address semantics |
| --- | --- | --- | --- | --- |
| Script, latest path | `GET /api/w/{workspace}/scripts/list` | `GET /api/w/{workspace}/scripts/get/p/{path}` | `POST /api/w/{workspace}/jobs/run/p/{path}` | Follows current deployed HEAD at the path |
| Script, pinned | list/get supplies a hash; `GET .../scripts/get/h/{hash}` | same hash endpoint | `POST /api/w/{workspace}/jobs/run/h/{hash}` | Immutable script revision |
| Flow, latest path | `GET /api/w/{workspace}/flows/list` | `GET /api/w/{workspace}/flows/get/{path}` | `POST /api/w/{workspace}/jobs/run/f/{path}` | Follows the currently deployed flow at the path |
| Flow, pinned | list/get supplies version; `GET .../flows/get/v/{version}` | same version endpoint | `POST /api/w/{workspace}/jobs/run/fv/{version}` | Numeric flow version |

The async execution endpoints accept JSON-compatible arguments and return `201 text/plain` with
the job UUID. The client validates the UUID before registering it. Synchronous
`run_wait_result` variants are excluded because they couple a Home Assistant action to arbitrary
job duration. [OAPI, WEBHOOKS, VERSIONING]

A selected runnable stores kind, path, addressing mode, and its hash/version when pinned.
Latest-path mode picks up deployments without reconfiguration but can change its input contract;
pinned mode is predictable but needs explicit reselection after a deployment. The initial UX
must make that trade-off visible rather than silently changing modes.

Script and flow models contain JSON-schema metadata. The safe discovery projection is limited to
parameter name, JSON type, required flag and bounded enum values. Descriptions, defaults,
examples, resource paths, arbitrary extension fields and schema values that look like credentials
are excluded until a later ticket proves a safe redaction policy.

## Least-privilege access map

Windmill granular scopes use `{domain}:{action}[:path]`; documented job execution scopes include
`jobs:run:scripts[:path]` and `jobs:run:flows[:path]`. Tokens without granular scopes inherit the
issuing user's permissions. Endpoint-specific enforcement is not fully expressed by OpenAPI, so
the table separates the token to recommend from the capability probe that proves it. [TOKENS]

| Product requirement | Needed operations | Recommended minimum token scope/role | Required? |
| --- | --- | --- | --- |
| PR-001 connection | `whoami`; optional workspace visibility/name | normal workspace member; restricted token needs `users:read`, plus `workspaces:read` when listing workspaces or resolving the name | Required |
| PR-002 capability negotiation | safe GET probes only | same token; no superadmin prerequisite | Required |
| PR-003 onboarding | PR-001 plus selected feature probes | union of enabled-feature scopes | Required |
| PR-004 health | public `/health/status`; detailed health | no token for coarse health; v1.775.2 detailed health is optional and reachable only with an effectively unscoped authenticated token because no `health` scope domain exists | Optional monitoring |
| PR-005 workers/groups | detailed health, optional worker/config endpoints | effectively unscoped token for detailed health in v1.775.2; `workers:read` for worker list; DevOps role plus `workers:read` for queue aggregates; `configs:read` for group list | Optional administrative monitoring |
| PR-006 runs | list/get jobs | `jobs:read`, still constrained by issuer visibility | Required when observation enabled |
| PR-007 scripts/flows | list/get only selected paths | `scripts:read:<path>` and/or `flows:read:<path>` where granular scopes are enabled | Required when discovery enabled |
| PR-008 execution | async run by selected path/hash/version | `jobs:run:scripts:<path>` and/or `jobs:run:flows:<path>`; hash/version enforcement must be instance-tested | Required when execution enabled |
| PR-009 cancel | job get/cancel | `jobs:read` plus `jobs:write`; handler additionally requires own/admin/RLS-visible per-job access | Required only for cancellation |
| PR-010 update | `/version`, `/uptodate` | no additional workspace permission; self-host only | Optional |
| PR-011 diagnostics | no additional Windmill call | none | Required locally |
| PR-012 security | all enabled calls | narrow union above; header-only token | Required |
| PR-013 reliability | same as enabled features | none additional | Required locally |
| PR-014 UX/distribution | no additional Windmill call | none | Required locally |
| PR-015 push, post-v1 | not selected yet | unknown until a separate threat/reliability study | Not in v1 |

Where a scope is called a candidate, onboarding must say that exact upstream enforcement remains
unverified and test it with the configured token. The integration must not advise users to create
a superadmin token merely to make optional diagnostics available.

## Cloud, Community Edition and Enterprise matrix

| Capability | Windmill Cloud | Self-hosted CE | Self-hosted EE |
| --- | --- | --- | --- |
| Workspace auth, scripts, flows, async jobs | Core; probe token visibility | Core | Core |
| `/version` | Probe; edition is not a product decision | `CE <version>` in pinned source | `EE <version>` in pinned source |
| Coarse/detailed instance health | Instance-global semantics may not be useful to a tenant; optional probe | Available in current release; old versions may return `404` | Available in current release; authorization is probed |
| Aggregate worker health | Optional detailed-health projection | Current detailed health | Current detailed health |
| Individual workers/group config | Cloud-managed and potentially tenant-inappropriate; optional probe | Current endpoints: authenticated worker list and group list, subject to visibility flags | Same pinned endpoints; advanced management remains out of scope |
| Queue metrics | Not needed for v1; DevOps-gated if exposed | Current endpoint is DevOps-gated; data presence is deployment-dependent | Current endpoint is DevOps-gated; optional |
| Update entity | `not_applicable` because Cloud is managed | `/version` plus best-effort `/uptodate` | Same |
| Upgrade action | Never | Never | Never |

This matrix intentionally avoids promising an endpoint from an edition label alone. [OAPI,
API-SRC, WORKERS]

## Errors, retries, limits and timeouts

The pinned OpenAPI documents success responses much more completely than error bodies. The typed
client therefore owns a small stable error taxonomy and must not deserialize arbitrary server
error bodies into entity state:

| Condition | Typed error | Retry policy |
| --- | --- | --- |
| URL/DNS/connect/TLS failure | `WindmillConnectionError` | Coordinator backoff |
| Client deadline | `WindmillTimeoutError` | Safe GET may retry; never blindly retry execute/cancel |
| `400` or `422` | `WindmillRequestError` | No automatic retry |
| `401` | `WindmillAuthenticationError` | Reauthentication |
| `403` | `WindmillAuthorizationError` | Disable optional capability or surface action error |
| `404` | `WindmillNotFoundError` | Distinguish endpoint probe from selected resource |
| `409` | `WindmillConflictError` | No automatic retry |
| `429` | `WindmillRateLimitError` | Honor valid bounded `Retry-After`; otherwise backoff |
| `5xx`/invalid gateway response | `WindmillServerError` | Retry idempotent GET with bounded jitter |
| Wrong content type/model/UUID | `WindmillProtocolError` | No immediate retry; expose bounded diagnostics |

No normative global Windmill API rate limit was found in the reviewed primary sources. Client
policy is explicit connect and total/read deadlines (initial proposal: 10 seconds to connect,
30 seconds total for ordinary calls), at most a small bounded retry count for idempotent GETs,
and coordinator backoff with jitter. These values require adjustment with tests; they are not
upstream guarantees. The server's `/uptodate` implementation itself has a ten-second GitHub
deadline, and health uses bounded database checks. [API-SRC, HEALTH-SRC]

Server error bodies and headers are untrusted. Diagnostics may retain status code, endpoint class,
typed error and a correlation/request ID if its format is safe; they must not retain response
bodies by default.

## Sensitive-data denylist

The following must never enter entity state, logs, event data or downloadable diagnostics:

- bearer tokens, cookies, approval tokens, query-string credentials and license strings;
- base URLs containing user-info, private query strings or other embedded credentials;
- job arguments, arbitrary results, logs, stack traces, raw code/flows and flow state;
- emails, `permissioned_as`, cancellation reasons and arbitrary labels/descriptions unless a
  later allowlist explicitly bounds them;
- worker IPs, last job/workspace IDs, resource/variable values, schema defaults/examples and
  arbitrary worker-group configuration;
- complete upstream error bodies or production payloads.

Config-entry data may contain the token because Home Assistant needs it, but diagnostics and
representations must redact it. URL rendering must omit user-info, query and fragments.

## Proposed sanitized test fixtures

Later client tickets should add static fixtures covering at least these shapes; all identifiers
are deliberately fake:

```json
{"status":"healthy","checked_at":"2026-08-01T10:00:00Z","database_healthy":true,"workers_alive":2}
```

```json
{
  "status":"degraded",
  "checked_at":"2026-08-01T10:00:00Z",
  "version":"CE 1.775.2",
  "checks":{
    "database":{"healthy":true,"latency_ms":3,"pool":{"size":4,"idle":2,"max_connections":20}},
    "workers":{"healthy":true,"active_count":2,"worker_groups":["default"],"min_version":"1.775.0","versions":["1.775.2"]},
    "queue":{"pending_jobs":1,"running_jobs":1},
    "readiness":{"healthy":true}
  }
}
```

```json
{"type":"QueuedJob","id":"00000000-0000-4000-8000-000000000001","running":true,"canceled":false,"job_kind":"script","permissioned_as":"u/example","is_flow_step":false,"email":"redacted@example.invalid","visible_to_owner":true,"tag":"deno","script_path":"u/example/lights"}
```

```json
{"type":"CompletedJob","id":"00000000-0000-4000-8000-000000000002","created_by":"example","created_at":"2026-08-01T10:00:00Z","started_at":"2026-08-01T10:00:01Z","completed_at":"2026-08-01T10:01:00Z","duration_ms":59000,"success":false,"canceled":false,"job_kind":"flow","permissioned_as":"u/example","is_flow_step":false,"is_skipped":false,"email":"redacted@example.invalid","visible_to_owner":true,"tag":"flow","script_path":"f/example/night"}
```

Also provide fixtures for `401`, `403`, `404`, `429` with and without valid `Retry-After`, `503`
health, malformed JSON, wrong content type, an invalid returned job UUID, nullable health checks,
pagination overlap, and responses containing denylisted sentinel secrets. Tests must assert those
sentinels never appear in logs or diagnostics.

## Proposed durable decisions

The research is sufficient to propose, but not accept, three ADRs:

1. **Async typed client and capability lattice** — a Home Assistant-independent async transport,
   allowlisted models, stable typed errors and per-capability five-state negotiation.
2. **Bounded polling for v1** — overlapping cursor windows, UUID deduplication and aggregate/event
   projection; no per-job entities and no inbound push dependency.
3. **Explicit runnable addressing** — persist latest-path versus pinned hash/version mode and never
   change it implicitly.

These become decisions only when the implementation ticket validates them against Home Assistant
interfaces and records an accepted ADR. No production code depends on an unaccepted ADR here.

## Implementation gates and remaining experiments

The following do not invalidate the source-backed contract, but the named ticket must close them
before relying on the capability:

| Experiment | Safe method | Owner |
| --- | --- | --- |
| Confirm public `/version` behavior and health availability on supported minimum versions | Public/no-token read-only slice observed in WMHA-0003; repeat at the eventual minimum version | WMHA-0005 compatibility gate |
| Confirm exact restricted-token scope for `whoami` | Disposable workspace/token before capability onboarding is exposed | WMHA-0004 |
| Confirm exact restricted-token scopes for hash/version execution and cancellation | Disposable workspace/token and target against a disposable deployment | WMHA-0009/0010 |
| Confirm detailed-health behavior for unscoped, granular-scoped and administrative tokens | Read-only probes; expect granular-scoped v1.775.2 tokens to fail before the handler; never log payloads | WMHA-0005 |
| Confirm Cloud tenant behavior for instance-global health/workers | Read-only probe on a test Cloud workspace | WMHA-0005/0006 |
| Validate `/uptodate` output and failure modes without depending on GitHub availability | Mocked client tests plus disposable self-host instance | WMHA-0011 |

An attempted read-only probe on 2026-08-01 using the provided SSH aliases `root@windmill` and
`root@homeassistant` did not reach either host because those aliases were not resolvable in the
agent environment. No remote command ran and no system was changed. Host access is therefore not
claimed as validation evidence.

A follow-up read-only probe on 2026-08-02 reached the user-provided test instance without reading
or sending credentials. The running CE `v1.768.0` server returned `200` for `/api/version` and
`/api/health/status?force=false`; detailed health, bounded worker listing and bounded workspace job
listing each returned `401` without a token. No response body from a protected endpoint was read,
no container or service was changed, and the observation does not replace the pinned v1.775.2
source contract. Restricted-token write behavior remains assigned to WMHA-0009 and WMHA-0010.
No disposable restricted token or Cloud test credential was available without reading or changing
existing credentials. Restricted-token `whoami` and capability presentation therefore remain an
explicit WMHA-0004 gate; detailed-health token variants and Cloud behavior remain explicit
WMHA-0005/0006 gates. The client never sends a token to the public `/version` endpoint, so a
"restricted-token version probe" is not part of its policy.

A follow-up live verification on 2026-08-02 (WMHA-0026, disposable local CE `v1.775.2`,
throwaway workspace, granular-scoped token minted via `POST /api/users/tokens/create`)
closed the restricted-token gates above:

- `whoami` onboarding and workspace listing succeeded with `users:read` + `workspaces:read`.
- Script and flow execution by path **and** by pinned hash/version all returned `201` with
  `jobs:run:scripts` / `jobs:run:flows` (domain-level, no path suffix needed); jobs completed
  `success`. The "instance test" caveat for hash/version enforcement is resolved.
- Cancellation returned `200` with `jobs:write` (plus `jobs:read`); the job was observed
  `canceled`.
- Detailed health with a granular-scoped token returned **`400`** with body "Could not
  extract domain from route: /api/health/detailed" — confirming the pinned-source prediction
  that scoped tokens fail in the scope middleware before the handler (no `health` domain
  exists), with the precise status code now observed. An unscoped token returned `200`.
  Note: at the time of the live check the client's capability discovery mapped this `400` to
  `unsupported` rather than `unauthorized`. Corrected 2026-08-03 (WMHA-0034 review of
  WMHA-0026): since WMHA-0030 (commit `e2f3395`) the detailed-health probe classifies exactly
  this `400` as `unauthorized`; no other `400` mapping changed.
- A token missing `workers:read` correctly produced `403` on the worker list, mapped by the
  client to `unauthorized` — the five-state capability behavior works against a live
  instance.
- A busy-workspace check (9 concurrent jobs: success/failure/canceled) confirmed the bounded
  job projection: UUID deduplication, correct outcome classification, and no payload fields
  (`args`, `result`, `logs`, `email`, `permissioned_as`) in the parsed model.
- One transient observation consistent with the WMHA-0015 propagation race: the `jobs/list`
  capability probe failed once when fired seconds after workspace creation, and succeeded on
  every repeat; not a client defect.
- Cloud tenant behavior remains unverified — no test tenant exists (human decision).

## Requirement traceability

| Requirement | Contract section |
| --- | --- |
| PR-001–PR-003 | Base URL/authentication, capabilities, least privilege |
| PR-004–PR-005 | Health/database/queue/workers and edition matrix |
| PR-006 | Jobs and run observation |
| PR-007–PR-009 | Runnable discovery/execution and job cancellation |
| PR-010 | Version/update discovery and edition matrix |
| PR-011–PR-012 | Typed errors and sensitive-data denylist |
| PR-013 | Pagination, timeout, retry and bounded polling policy |
| PR-014 | No additional API contract; translations/distribution are local concerns |
| PR-015 | Deferred; proposed polling ADR explicitly avoids a v1 push dependency |
