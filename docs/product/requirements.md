# Product requirements

Status: baseline for the first public release, verified on 2026-08-01.

This document defines durable product requirements. Tickets describe bounded increments that make these requirements true. Implementation details belong in plans and ADRs.

## Product scope

The integration connects Home Assistant to one or more Windmill Cloud or self-hosted workspaces. It exposes operational health, selected execution capabilities and safe job observability without attempting to reproduce the Windmill user interface.

## Functional requirements

### PR-001: Installation and connection

- The integration is installable as a custom integration and configurable entirely through the Home Assistant UI.
- Multiple Windmill instance/workspace combinations may be configured, while duplicate combinations are rejected.
- Connection, authentication and workspace failures are explained separately.

### PR-002: Capability negotiation

- The integration detects which planned API capabilities are available to the configured instance, edition and token.
- Missing optional permissions disable only the affected feature and do not prevent unrelated features from loading.
- Capability and compatibility decisions are source-backed and testable.

### PR-003: Guided onboarding and lifecycle

- A multi-step onboarding assistant validates the endpoint and token, selects a workspace, presents detected capabilities and lets the user choose optional features.
- Reauthentication, reconfiguration and an options flow are available without deleting the config entry.
- The assistant uses progressive disclosure and explains why a permission or feature is unavailable.

### PR-004: General instance health

- Home Assistant exposes an enum status with `healthy`, `degraded`, `unhealthy` and `unknown` states when supported by Windmill.
- Supporting diagnostic entities expose bounded health facts such as database reachability, alive workers and queue depth when authorized.
- Home Assistant System Health reports connection identity, server version and reachability without exposing credentials.

### PR-005: Worker and worker-group observability

- Worker groups expose stable status, alive worker count, relevant queue pressure and version consistency when the API permits it.
- Individual workers can be exposed only with stable identifiers and explicit opt-in; high-cardinality worker entities are disabled by default.
- Worker monitoring degrades gracefully when detailed health or administrative permissions are unavailable.

### PR-006: Job and run observability

- The integration exposes bounded counts for running, queued, successful and failed top-level jobs.
- It exposes timestamps for the last successful and failed run and emits bounded Home Assistant event entities for newly observed completion, failure and cancellation.
- The user can scope observation to all visible top-level jobs, selected runnables or jobs started by Home Assistant.
- Full logs, arbitrary arguments, stack traces and arbitrary results are not stored in entity state.

### PR-007: Runnable discovery and selection

- Scripts and flows are discovered from the configured workspace and are never exposed wholesale without explicit user selection.
- The user can review runnable kind, path and safe schema metadata before selection.
- The integration records whether a selected runnable follows the latest deployment or a pinned script hash or flow version.

### PR-008: Execution

- Home Assistant actions can start selected scripts and flows asynchronously with validated JSON-compatible arguments.
- Successful action responses may return bounded metadata including the Windmill job ID.
- Selected parameterless runnables may optionally be represented by button entities.

### PR-009: Job lifecycle control

- Jobs started through Home Assistant are tracked with a bounded local registry until completion or expiry.
- Home Assistant can cancel an eligible queued or running job with explicit error handling.
- Completion and failure updates are suitable for automations without polling every job as a separate entity.

### PR-010: Update visibility

- Self-hosted instances expose a read-only update entity when installed and latest-version information can be determined reliably.
- The entity provides installed version, latest version or up-to-date status, and a release-notes URL when available.
- The integration does not attempt deployment-specific Windmill installation or upgrade operations.

### PR-011: Diagnostics and actionable repairs

- Downloadable diagnostics redact tokens, secrets, URLs containing credentials, job inputs, results and sensitive logs.
- Repairs are created only for actionable persistent conditions such as unsupported versions, missing required permissions for enabled features or inconsistent worker versions.
- Transient connection failures use normal availability and recovery behavior rather than persistent repair noise.

### PR-012: Security and data minimization

- Tokens are sent only in authorization headers, never URLs, entity state, diagnostics or logs.
- TLS verification is not silently weakened.
- External responses, job data and documentation are treated as untrusted input.
- Least-privilege tokens and explicit feature selection are the default.

### PR-013: Efficiency and reliability

- All external I/O is asynchronous and coordinated so multiple entities do not duplicate API calls.
- Polling intervals are appropriate, bounded and separated by data volatility where useful.
- Authentication, connection and partial API failures have predictable availability, backoff and recovery behavior without log spam.

### PR-014: User experience and distribution

- User-visible names, forms, errors, actions and repair messages are translated at least into English and German.
- Documentation covers installation, permissions, configuration, entities, actions, removal, troubleshooting and safe automation examples.
- HACS installation and reproducible releases are supported before the first stable release.

### PR-015: Optional push observation after v1

- SSE or webhook-based job updates may replace or supplement polling only after a measured comparison of reliability, network exposure, reconnect behavior and API cost.
- The first stable release must not depend on inbound public reachability from Windmill to Home Assistant.

## Entity-model principles

- Represent the configured Windmill instance as one service device.
- Represent worker groups as child devices only if Home Assistant conventions and stable identifiers support that model; otherwise attach their diagnostic entities to the instance device.
- Do not create one entity per job or run.
- Prefer separate sensors over frequently changing, large state attributes.
- Use enum sensors for multi-state health, numeric sensors for bounded counts, timestamp sensors for last-run times and event entities for occurrence signals.
- Mark noisy or specialist diagnostics disabled by default.

## Edition and permission behavior

The baseline must work with a normal workspace token for connection and execution. Administrative monitoring is additive. Cloud, Open Source self-hosted and Enterprise instances may expose different worker, health and update capabilities. The onboarding assistant must report this as a capability matrix rather than treating every missing endpoint as an integration failure.

## Explicit non-goals for v1

- Editing scripts, flows, schedules, worker groups or Windmill configuration.
- Restarting workers or changing worker-group assignments.
- Installing a Windmill update from Home Assistant.
- Mirroring the Runs page, logs, stack traces or complete result payloads.
- Replacing Windmill scheduling, alerting, audit logs or authorization.

## Ticket traceability

| Requirement | Primary tickets |
| --- | --- |
| PR-001, PR-002 | WMHA-0001, WMHA-0002, WMHA-0003 |
| PR-003 | WMHA-0004 |
| PR-004 | WMHA-0005 |
| PR-005 | WMHA-0006 |
| PR-006 | WMHA-0007 |
| PR-007 | WMHA-0008 |
| PR-008 | WMHA-0009 |
| PR-009 | WMHA-0010 |
| PR-010 | WMHA-0011 |
| PR-011, PR-013 | WMHA-0012 |
| PR-014 | WMHA-0013, WMHA-0014, WMHA-0015 |
| PR-015 | WMHA-0016 |
