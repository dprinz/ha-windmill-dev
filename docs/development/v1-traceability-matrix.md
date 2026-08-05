# v1 requirement traceability matrix

Status: release-gate evidence for WMHA-0015, compiled 2026-08-02.

This matrix maps every v1 product requirement (`docs/product/requirements.md`, PR-001 through
PR-014) to the tickets that implement it and to the concrete evidence that it works. PR-015 is
post-v1 by product decision (backlog ticket WMHA-0016) and is out of scope here.

Statuses:

- **implemented** — code, tests and documentation exist and are cited.
- **implemented with live gap** — implemented and test-covered, but a source-backed live-instance
  check is still outstanding; each is listed under "Outstanding live checks" and in the known
  limitations document.
- **deferred** — deliberately not part of v1, with the decision and its location.

## Matrix

| Requirement | Status | Implementing tickets | Evidence |
| --- | --- | --- | --- |
| PR-001 Installation and connection | implemented with live gap | WMHA-0002, WMHA-0003, WMHA-0004 | UI-only config flow with duplicate-identity rejection and separate connection/auth/workspace errors: `tests/test_config_flow.py` (`test_connection_step_error_mapping`, `test_workspace_step_error_mapping`, `test_duplicate_identity_is_rejected`, `test_guided_onboarding_creates_entry`); README Installation/Configuration. Live gap: restricted-token onboarding check not run (WMHA-0004 evidence). |
| PR-002 Capability negotiation | implemented | WMHA-0003, ADR-0001 | Five-state capability matrix per entry: `tests/test_capabilities.py`, `custom_components/windmill/models.py`, `custom_components/windmill/coordinator.py`; decisions source-backed by `docs/research/windmill-api-contract.md`. |
| PR-003 Guided onboarding and lifecycle | implemented | WMHA-0004 | Multi-step onboarding with capability presentation and progressive disclosure; reauth, reconfigure and options flow without deleting the entry: `tests/test_config_flow.py` (`test_reauth_updates_token_and_reloads`, `test_reauth_keeps_every_user_option`, `test_reauth_failure_keeps_stored_token`, `test_reconfigure_*`, `test_options_flow_*`). |
| PR-004 General instance health | implemented with live gap | WMHA-0005 | Enum health sensor with `healthy`/`degraded`/`unhealthy`/`unknown`, bounded diagnostic sensors, System Health without credentials: `tests/test_health.py`, `tests/test_system_health.py`, `custom_components/windmill/sensor.py`, `custom_components/windmill/system_health.py`. Live gap: detailed-health behavior for granular/admin tokens and Cloud tenant health not run (WMHA-0005 evidence). |
| PR-005 Worker and worker-group observability | implemented with live gap | WMHA-0006, WMHA-0021, ADR-0002 | Per-group sensors plus opt-in per-instance sensors (off by default, stable IDs), graceful degradation on 403/404: `tests/test_workers.py` (incl. `test_configured_group_without_workers_reports_zero`, `test_silent_instance_keeps_its_entity_and_reports_zero`, `test_new_instance_needs_a_reload`). Live gap: Cloud tenant worker behavior not run (WMHA-0006 evidence). |
| PR-006 Job and run observability | implemented with live gap | WMHA-0007, WMHA-0017, WMHA-0018, WMHA-0022, WMHA-0023 | Bounded running/queued/success/failed counts, last-success/last-failure timestamps, bounded event entities for completion/failure/cancellation, three-way observation scope, no logs/args/results in state: `tests/test_runs.py`, `tests/test_lifecycle.py`; retention model in `plans/WMHA-0007.md`. Live gap: busy-workspace observation not run (WMHA-0007 evidence). |
| PR-007 Runnable discovery and selection | implemented | WMHA-0008 | Explicit user selection only, safe schema projection (name/type/required/bounded enum), latest-vs-pinned addressing recorded: `tests/test_runnables.py`; conditional flow pinning rationale in `plans/WMHA-0008.md`. |
| PR-008 Execution | implemented with live gap | WMHA-0009, WMHA-0019 | `windmill.run` action with validated JSON-compatible arguments and bounded response incl. job ID; optional parameterless buttons: `tests/test_execution.py`. Live gap: restricted-token hash/version execution not run (WMHA-0009 evidence). |
| PR-009 Job lifecycle control | implemented with live gap | WMHA-0010, WMHA-0019 | Bounded registry (50 jobs / 24 h) persisted in a HA store, cancel action with distinct error mapping, completion events for automations: `tests/test_lifecycle.py` (incl. `test_only_started_jobs_are_tracked_and_cancellable`, `test_registry_is_bounded_by_size_and_age`, `test_registry_survives_reload_without_duplicate_events`). Live gap: restricted-token cancellation authorization not run (WMHA-0010 evidence). |
| PR-010 Update visibility | implemented | WMHA-0011 | Read-only update entity (installed/latest/release URL), eligibility conjunction (opt-in + successful probe + non-Cloud), no install/upgrade operation: `tests/test_update.py`. Live `/api/uptodate` output observed in the WMHA-0015 smoke (`v1.775.2` → `v1.776.0`); parsing covered by mocked tests for four parametrized body shapes plus unparseable text and a missing endpoint (`tests/test_api.py:1119-1170`). |
| PR-011 Diagnostics and actionable repairs | implemented | WMHA-0012 | Downloadable diagnostics with redaction; derived-not-asserted repairs for unsupported version, missing permissions, worker-version drift; transient failures stay availability-based: `tests/test_diagnostics.py`, `tests/test_issues.py`, `custom_components/windmill/diagnostics.py`, `custom_components/windmill/issues.py`. |
| PR-012 Security and data minimization | implemented with live gap | WMHA-0003, WMHA-0012, all feature tickets | Header-only bearer token, no token query parameters, TLS verification unchanged, allowlist job parsing with denylist sentinel tests, redacted diagnostics: `tests/test_api.py`, `tests/test_diagnostics.py`; denylist in `docs/research/windmill-api-contract.md`; verified independently in the WMHA-0015 security review (Block 4 evidence below). Live gap: same outstanding live checks as PR-001/008/009. |
| PR-013 Efficiency and reliability | implemented | WMHA-0003, WMHA-0012 | Shared coordinators (no duplicated API calls per entity), separated polling intervals, coordinator backoff with jitter, rate-limit `Retry-After` handling: `custom_components/windmill/coordinator.py`, `tests/test_init.py`, `tests/test_issues.py`; backoff invariant recorded in `docs/development/handoff-after-WMHA-0012.md`. |
| PR-014 User experience and distribution | implemented, one deferral | WMHA-0013, WMHA-0014, WMHA-0024, WMHA-0025 | English and German translations with guardrail-enforced key parity; README covering installation, permissions, configuration, entities, actions, removal, troubleshooting, automation examples; HACS packaging, reproducible release build, green HACS/hassfest CI: `custom_components/windmill/translations/`, `README.md`, `.github/workflows/`, `scripts/build_release.py`; CI runs 30758630293/30758630322 green on `main` 2026-08-02. Deferred: submission to the HACS default store — deliberate follow-up per `docs/research/hacs-and-release-requirements.md` (R-007); custom-repository installation is the documented v1 path. |

## Outstanding live checks (inherited from feature tickets)

WMHA-0015 ran a client-level live smoke against a disposable local Windmill CE `v1.775.2`
(2026-08-02; method and output in `docs/product/supported-versions-and-limitations.md`). It
closed or narrowed the following gates recorded in `docs/research/windmill-api-contract.md`:

- **Closed:** real `/api/uptodate` output and failure modes (WMHA-0011) — live response
  `Update`-style output parsed to `installed=v1.775.2, latest=v1.776.0`.
- **Closed at superadmin level:** script execution and job cancellation end-to-end against a live
  instance (WMHA-0009/WMHA-0010) — but with a throwaway superadmin token, not a restricted one.
- **Confirmed live:** public no-token `/api/version` and `/api/health/status`, whoami validation,
  five-state capability discovery (execution/cancellation correctly `not_applicable` before
  target selection), detailed health with an unscoped token, worker groups and worker listing.

Still open after WMHA-0015 — **all four resolved or re-confirmed by WMHA-0026 on 2026-08-02**
(live checks against a disposable local CE `v1.775.2` with a granular-scoped token; method and
dated results in the WMHA-0026 ticket and `docs/product/supported-versions-and-limitations.md`):

1. ~~Restricted-token (least-privilege) onboarding, execution and cancellation against a live
   instance (WMHA-0004/0009/0010)~~ — **closed 2026-08-02:** granular-scoped token
   (`users:read`, `workspaces:read`, `jobs:read`, `jobs:write`, `jobs:run:scripts`,
   `jobs:run:flows`, `scripts:read`, `flows:read`) succeeded for whoami onboarding, workspace
   listing, script/flow execution by path and by pinned hash/version (all `201`), and
   cancellation (`200`, observed `canceled`).
2. ~~Detailed-health behavior for granular-scoped tokens (WMHA-0005)~~ — **closed 2026-08-02:**
   granular-scoped token → `400` from the scope middleware (no `health` domain, as the pinned
   source predicted); unscoped token → `200`. The `400` surfaced as `unsupported` instead of
   `unauthorized` in capability discovery; fixed in WMHA-0030 (commit `e2f3395`), so capability
   discovery now reports it as `unauthorized` (corrected 2026-08-03 by the WMHA-0034 review).
3. ~~Cloud tenant behavior for health and workers (WMHA-0005/0006)~~ — **closed 2026-08-05
   (WMHA-0045):** a throwaway Cloud tenant (`EE v1.779.0`) was provisioned and now runs as a
   config entry in a real Home Assistant installation. Health, detailed health, workers, runs and
   script/flow discovery all probed `available`; `managed_cloud` was detected correctly and
   suppressed the update entity. Availability of the two administrative probes depends on the
   token, not on Cloud. Execution and cancellation on Cloud remain without a live run.
4. ~~Observation against a busy real workspace (WMHA-0007)~~ — **closed at synthetic-load level
   2026-08-02:** 9 concurrent jobs (success/failure/canceled) on a disposable workspace were all
   deduplicated and correctly classified through the bounded projection, with no payload fields
   in the parsed model. Production-scale observation remains out of reach by design.

These are evidence gaps, not implementation gaps, and are published as release risks in
`docs/product/supported-versions-and-limitations.md`.

## Deferred by reviewed product decision

- PR-015 push observation — post-v1, backlog ticket WMHA-0016.
- HACS default-store inclusion — follow-up after release; custom repository path documented.
- Queue metrics time series (`/api/workers/queue_metrics`) — not required for v1 per the API
  contract; bounded current counts from detailed health are used instead.

## Findings

No requirement was found unimplemented without an explicit, documented decision. The genuine
gaps are the live checks above; they are evidence gaps, not implementation gaps, and are
published as release risks rather than hidden.
