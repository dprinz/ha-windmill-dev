# Supported versions and known limitations

Current integration release: `0.3.1` (public beta).

Status: public compatibility statement for release 0.3.1, updated on 2026-08-05. It states only
what the available contract checks, automated tests and live evidence support. Since 0.3.1 that
evidence includes two config entries running in a real Home Assistant installation — one
self-hosted, one Windmill Cloud. The integration is ready for public testing, but its external
installation base is still small.

## Supported Home Assistant versions

| Home Assistant | Status | Evidence |
| --- | --- | --- |
| 2026.7.4 | tested + live | pinned test baseline (`pytest-homeassistant-custom-component==0.13.348`, Python 3.14); the full 439-test suite runs against it, and release 0.3.1 runs live on Home Assistant OS 18.1 / core 2026.7.4 / Python 3.14.6 (see below) |
| 2026.7.0 and newer 2026.7.x | supported | `hacs.json` minimum `2026.7.0` |
| older than 2026.7.0 | untested | not claimed |

## Supported Windmill versions and editions

| Windmill | Status | Evidence |
| --- | --- | --- |
| Self-hosted CE `v1.775.2` | verified contract + live smoke | API contract verified line-by-line against the pinned upstream sources (`docs/research/windmill-api-contract.md`); live client-level smoke against a local disposable Docker deployment on 2026-08-02 (see below) |
| Self-hosted CE `v1.768.0` | live end-to-end in Home Assistant | read-only probe on 2026-08-02, live observation of the `jobs/list` response shape on 2026-08-04 (which produced the run-observation fix released in 0.1.3), and a continuously running config entry in Home Assistant since 2026-08-04 (see below) |
| Self-hosted EE | contract-level | same pinned source; edition differences are capability-probed at runtime; no live EE instance was available |
| Older self-hosted versions | degraded by design | endpoints introduced after a server's version probe as `unsupported` and disable only the affected feature; no minimum version is claimed |
| Windmill Cloud (`EE v1.779.0`) | live end-to-end | Running config entry in Home Assistant since 2026-08-05, plus a live client-driven run of script execution by path and by pinned hash, and of cancellation (see below). Flow execution has no live Cloud run |

### Live smoke evidence (2026-08-02, disposable local CE `v1.775.2`)

Method: official `docker-compose.yml` from the Windmill repository at tag `v1.775.2`, image
`ghcr.io/windmill-labs/windmill:1.775.2`, bound to localhost only, with a throwaway workspace
(`smoke`) and a throwaway superadmin session token on a fresh database. The integration's own
`WindmillClient`/`WindmillInstanceClient` drove every check. Containers, volumes and images were
removed afterwards; no credential was committed. This is a client-level smoke, not a full Home
Assistant end-to-end run — that boundary is stated deliberately. It was crossed on 2026-08-05 by
the running-installation evidence below.

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

### Live Home Assistant evidence (2026-08-05, release 0.3.1)

Two config entries running in one real Home Assistant installation — Home Assistant OS 18.1,
core `2026.7.4`, Python 3.14.6, `amd64` — read from the integration's own diagnostics. This is
the first evidence from a full Home Assistant runtime rather than a client-level smoke.

| | Self-hosted CE `v1.768.0` | Windmill Cloud `EE v1.779.0` |
| --- | --- | --- |
| Entry state | `loaded` | `loaded` |
| Instance identity | `edition: ce`, `managed_cloud: false`, superadmin | `edition: ee`, `managed_cloud: true`, workspace admin |
| Health / detailed health / workers | `available` | `available` |
| Runs / script discovery / flow discovery | `available` | `available` |
| Update visibility | `available` | `available` |
| Execution / cancellation | `not_applicable` (`context_required`) | `not_applicable` (`context_required`) |

Additionally observed:

- **Every enabled coordinator reports `last_update_success: true`.** On the self-hosted entry that
  is all seven — capabilities (6 h), health (60 s), workers (120 s), runs (60 s), runnables
  (30 min), runnable runs (5 min) and update (6 h); on Cloud the three enabled ones.
- **`runnable_details` runs live** on the self-hosted entry with one selected runnable in `latest`
  mode, as do `worker_groups` and the update entity.
- **The update entity works against a real server**: `v1.768.0` installed, `v1.780.0` latest, read
  from `/api/uptodate`.
- **Cloud detection works.** The Cloud entry is correctly classified `managed_cloud: true` from
  `app.windmill.dev`, so the update entity is suppressed there exactly as designed — the first
  live confirmation of that branch.
- **The plain-HTTP repair issue fires live** (`insecure_transport`) for the self-hosted entry,
  which is reached over `http://` — the WMHA-0036 behavior confirmed outside tests.

Not covered by this evidence: `runnable_buttons`, `worker_details`, and the detailed-health
entities, whose options are off on both entries. Execution and cancellation are covered by the
separate Cloud run below.

### Live Cloud execution and cancellation (2026-08-05, `EE v1.779.0`)

Capability discovery deliberately never probes execution, so this needed its own run. The
integration's own `WindmillClient` drove every step against `app.windmill.dev` on a throwaway
account, using a disposable Deno script that sleeps for a requested number of seconds:

| Step | Result |
| --- | --- |
| `async_connect` | `ee v1.779.0` |
| `async_list_runnables` | 1 script, target found |
| `async_get_runnable` | hash resolved, 1 input parameter parsed |
| `async_run_runnable` by path | job started, observed `success`, `duration_ms=69` |
| `async_run_runnable` by pinned script hash | job started, observed `success` |
| `async_cancel_job` on a 300-second job | accepted, observed `canceled` |

Each completion was observed through the same bounded `jobs/list` projection the run entities
use, so the run-observation path is covered on Cloud as well. Flow execution was not run: the
workspace has no flow, and the flow path differs from the script path only in the target segment,
which is covered by tests and by the 2026-08-02 self-hosted smoke.

One correction this evidence forced: an earlier draft of this document predicted that detailed
health and worker details would stay unavailable on Windmill Cloud, because a workspace-bound
token is refused on the instance-wide endpoints. Both probes returned `available` on Cloud with
the token actually configured. Cloud availability therefore depends on the token, not on Cloud.

## Known limitations

These are accepted, documented trade-offs of the current public beta. Each links its source.

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
5. **Update entity eligibility.** The update entity never appears for Windmill Cloud — confirmed
   live on 2026-08-05, where `app.windmill.dev` was classified `managed_cloud: true` and the
   entity was suppressed. A Cloud tenant behind a custom domain still cannot be detected, so
   `update_entity` stays a deliberate opt-in. The `/api/uptodate` check depends on the server
   reaching GitHub; any failure maps to `unknown`, never to an error (WMHA-0011).
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
11. **A very large queue stops run observation.** Windmill's `jobs/list` returns the entire queue
    alongside the requested completed rows, and it is not paginated. A workspace with hundreds of
    simultaneously queued jobs exceeds the client's row and response-size bounds, so the run poll
    fails closed and retries; the run entities become unavailable until the queue drains. Health,
    workers and execution are unaffected (WMHA-0038).
12. **A retried job is not matched to its runnable.** Windmill re-pushes a failed job that has a
    retry policy as a single-step flow (`job_kind = "singlestepflow"`) on the original path, so it
    matches neither the per-runnable detail entities nor the `selected` run scope, both of which
    compare kind and path. For a selected script with retries, the detail entities keep showing
    the first failed attempt and the successful retry stays invisible. Found by review, not by a
    live reproduction; widening the match needs live evidence first (WMHA-0044).

## Evidence gaps carried into the public beta

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
- ~~Windmill Cloud has no live coverage~~ **Closed 2026-08-05 (WMHA-0045):** a throwaway Cloud
  account was provisioned and a config entry now runs against `app.windmill.dev`
  (`EE v1.779.0`) in a real Home Assistant installation. Connection, capability discovery,
  instance health, run observation and script/flow discovery are live-verified; Cloud detection
  correctly suppresses the update entity; and a separate client-driven run covered script
  execution by path and by pinned hash plus cancellation. **What remains open:** flow execution
  has no live Cloud run, and no Cloud entry has yet been observed across a Home Assistant restart
  or a token rotation.
- **Not verified: the WMHA-0045 fallback itself on Cloud.** The fix makes a `401` from the
  instance-wide workspace listing degrade to manual workspace entry. The Cloud entry above was
  created after the fix shipped, but its token reaches the instance-wide endpoints (both optional
  probes returned `available`), so it is not established that this particular setup exercised the
  fallback. The mapping is covered by unit tests and by the live probe recorded in WMHA-0045;
  an end-to-end Cloud run with a token that cannot list workspaces is still missing.
