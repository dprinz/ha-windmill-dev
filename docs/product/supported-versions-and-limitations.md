# Supported versions and known limitations (v1)

Status: release-gate statement for the first stable release, compiled for WMHA-0015 on
2026-08-02. This page is the public compatibility statement required before release approval.
It states only what evidence supports.

## Supported Home Assistant versions

| Home Assistant | Status | Evidence |
| --- | --- | --- |
| 2026.7.4 | tested | pinned test baseline (`pytest-homeassistant-custom-component==0.13.348`, Python 3.14); the full 385-test suite runs against it |
| 2026.7.0 and newer 2026.7.x | supported | `hacs.json` minimum `2026.7.0` |
| older than 2026.7.0 | untested | not claimed |

## Supported Windmill versions and editions

| Windmill | Status | Evidence |
| --- | --- | --- |
| Self-hosted CE `v1.775.2` | verified contract + live smoke | API contract verified line-by-line against the pinned upstream sources (`docs/research/windmill-api-contract.md`); live client-level smoke against a local disposable Docker deployment on 2026-08-02 (see below) |
| Self-hosted CE `v1.768.0` | public probes observed | read-only probe on 2026-08-02: `/api/version` and `/api/health/status` returned 200; protected endpoints returned 401 without a token (`docs/research/windmill-api-contract.md`) |
| Self-hosted EE | contract-level | same pinned source; edition differences are capability-probed at runtime; no live EE instance was available |
| Older self-hosted versions | degraded by design | endpoints introduced after a server's version probe as `unsupported` and disable only the affected feature; no minimum version is claimed |
| Windmill Cloud | unverified — release risk | no Cloud test tenant exists; behavior is designed from the contract (update entity `not_applicable`, instance-global health optional) but has no live coverage; re-confirmed unverifiable on 2026-08-02 (WMHA-0026) |

### Live smoke evidence (2026-08-02, disposable local CE `v1.775.2`)

Method: official `docker-compose.yml` from the Windmill repository at tag `v1.775.2`, image
`ghcr.io/windmill-labs/windmill:1.775.2`, bound to localhost only, with a throwaway workspace
(`smoke`) and a throwaway superadmin session token on a fresh database. The integration's own
`WindmillClient`/`WindmillInstanceClient` drove every check. Containers, volumes and images were
removed afterwards; no credential was committed. This is a client-level smoke, not a full Home
Assistant end-to-end run — that boundary is stated deliberately.

Observed (full output in the WMHA-0015 ticket evidence):

- Public probes without any token: `GET /api/version` → `200 CE v1.775.2`;
  `GET /api/health/status?force=false` → `200 healthy` — confirms the client contract that these
  endpoints need no token.
- `async_get_server_info` → `CE v1.775.2`; `async_list_workspaces` → `['smoke']`;
  `async_validate` (whoami) → superadmin identity parsed.
- `async_discover_capabilities` → health, detailed health, workers, runs, script/flow discovery
  and update visibility `available`; script/flow execution and cancellation `not_applicable`
  before target selection — exactly the ADR-0001 five-state behavior.
- `async_get_detailed_health` → `healthy` with an unscoped token, matching the pinned scope
  middleware prediction.
- `async_list_worker_groups` → `('reports', 'native', 'default')`; `async_list_workers` →
  9 alive workers.
- `async_get_update_status` → `up_to_date=False, installed=v1.775.2, latest=v1.776.0` — the first
  live observation of the real `/api/uptodate` output; it matches the mocked parser contract
  (closes the WMHA-0011 live gap).
- Execution: a trivial disposable Deno script ran through `async_run_runnable`; the job completed
  `success` and was observed through the bounded job listing (`duration_ms=108`).
- Cancellation: a long-running disposable script was cancelled through `async_cancel_job` and
  observed as `canceled` through the bounded job listing.
- Minor observation, not a defect: running a script in the same second it was created returned
  `404` once; retrying moments later succeeded (upstream propagation race). The client maps this
  to a distinct typed error, so setup and actions report it cleanly.

Cloud coverage is absent and is a stated release risk, not a hidden assumption.

## Known limitations

These are accepted, documented trade-offs of v1. Each links its source.

1. **Cancellation events under the `home_assistant_started` scope.** When you cancel a job through
   the integration's own cancel action, no `canceled` event is emitted under that scope, because
   the job is forgotten immediately and the scope filter drops its completion. You already
   received the action result; under the `all` scope the event fires normally
   (WMHA-0017, accepted residual risk).
2. **Only the newest pending completion survives a bootstrap poll.** A completion observed by the
   refresh during setup is delivered once Home Assistant has started, and a failing poll in between
   no longer discards it (WMHA-0032 closed that loss window; the publication guard waits for
   startup instead of for a successful poll). What remains: while the integration is unavailable or
   still starting, only the most recent observed completion keeps its state write, so a poll that
   observes a newer completion in that window supersedes the pending one. Duplicate delivery stays
   impossible in every case (WMHA-0022/WMHA-0023/WMHA-0032).
3. **Worker entities are fixed at setup.** Worker groups or instances created in Windmill after
   setup get entities only after a reload. A silent worker keeps its entity and reports `0`.
   Deployments with ephemeral `worker_instance` identifiers accumulate permanently-zero entities
   across reloads; `worker_details` is therefore opt-in and off by default
   (ADR-0002, README *Worker entity lifecycle*).
4. **More than 500 alive workers.** Worker counting walks at most five pages of 100; beyond that,
   counts are a documented lower bound (client policy).
5. **Update entity eligibility.** The update entity never appears for Windmill Cloud, but a Cloud
   tenant behind a custom domain cannot be detected; `update_entity` stays a deliberate opt-in.
   The `/api/uptodate` check depends on the server reaching GitHub; any failure maps to `unknown`,
   never to an error (WMHA-0011).
6. **Worker version drift grace period.** The worker-version repair fires only after 30 minutes of
   drift so rolling upgrades stay quiet; the 30 minutes are a judgement, not a measurement
   (WMHA-0012).
7. **Diagnostics need a loaded entry.** Home Assistant only offers diagnostics for loaded entries;
   an entry that fails to set up cannot be diagnosed through the download (Home Assistant
   constraint, WMHA-0012).
8. **Button-started jobs share the registry bound.** Frequently pressed runnable buttons consume
   slots of the 50-job started-job registry faster; a still-running job may be evicted earlier
   (WMHA-0019).
9. **Orphaned pre-release stores.** Store files from add-and-remove cycles before the removal
   cleanup existed are not deleted retroactively; they are small, never read again and removable
   by hand (WMHA-0020, README *Removing the integration*).
10. **Same-millisecond completions share the event state string.** Two completions observed in
    the same millisecond produce the same event-entity state; their attributes always differ by
    `job_id`, so nothing is lost and state-trigger automations still fire for both (WMHA-0018).

## Evidence gaps carried into the release

Recorded honestly instead of claimed:

- ~~Restricted-token (least-privilege) execution and cancellation~~ **Closed 2026-08-02
  (WMHA-0026 live check, disposable CE `v1.775.2`):** a granular-scoped token
  (`users:read`, `workspaces:read`, `jobs:read`, `jobs:write`, `jobs:run:scripts`,
  `jobs:run:flows`, `scripts:read`, `flows:read`), minted through
  `POST /api/users/tokens/create` on a throwaway workspace, drove the integration's own
  client successfully: whoami onboarding, workspace listing, script and flow execution by
  path **and** by pinned hash/version (all `201`, jobs completed `success`), and
  cancellation (`200`, job observed `canceled`). Capability discovery mapped the missing
  `workers:read` scope correctly to `unauthorized`.
- ~~Detailed-health behavior for granular-scoped tokens~~ **Closed 2026-08-02 (WMHA-0026):**
  a granular-scoped token receives `400` ("Could not extract domain from route:
  /api/health/detailed") — it fails in the scope middleware before the handler, exactly as
  the pinned source predicted; an unscoped token receives `200`. Detailed health therefore
  stays an optional capability that needs an effectively unscoped token. Since WMHA-0030 the
  detailed-health probe classifies exactly this `400` as `unauthorized` (token scope cannot
  address the route) instead of `unsupported`; no other `400` mapping changed.
- ~~No observation of a busy production workspace~~ **Narrowed 2026-08-02 (WMHA-0026):** a
  busy disposable workspace with real concurrent traffic (6 successful, 2 failed, 1
  cancelled job) was observed through the client's bounded projection: all 9 jobs were
  deduplicated by UUID and classified correctly, and no payload fields (args, results,
  logs, emails) entered the parsed model. This is still a synthetic load, not production
  scale; the polling bounds remain client policy validated by tests.
- Windmill Cloud has no live coverage (see above) — **re-confirmed unverifiable 2026-08-02
  (WMHA-0026):** no Cloud test tenant could be obtained without production credentials;
  provisioning one remains a human decision.
