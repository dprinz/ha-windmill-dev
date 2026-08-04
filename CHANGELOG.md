# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- New opt-in feature `runnable_details`. Every script and flow selected under
  **Configure → Scripts and flows** becomes its own device below the workspace
  device, with `Last run`, `Last status`, `Last duration`, `Next run` and
  `Running`. Unlike the workspace-wide run observation, these answer for one
  runnable in particular, including one that last ran days ago.
- `Next run` is read from the job Windmill reserves in its own queue for the
  next occurrence of a schedule. The integration neither reads nor writes
  schedules and never evaluates a cron expression; a runnable without a
  schedule reports nothing.

### Fixed

- The workspace `Queued jobs` sensor no longer counts the next occurrence of
  every enabled schedule. Windmill writes those into the queue as soon as the
  previous run finishes, so an idle workspace reported a queue depth equal to
  its number of schedules and never reached zero. Only jobs actually waiting
  for a worker are counted now. If an automation depended on the old number,
  it will see lower values.
- The workspace device is registered during setup instead of being created as
  a side effect of the first entity that referenced it. With every
  workspace-level feature disabled, no entity created it at all.

## [0.1.3] - 2026-08-04

### Fixed

- Run observation is no longer reported as unsupported on a workspace that has
  jobs. Windmill's `jobs/list` applies `per_page` only to the completed half of
  its `queue UNION ALL completed` response and returns the entire queue on top,
  so a single running job made the capability probe reject a perfectly healthy
  answer. Setup then showed `Runs: unsupported`, the run entities were never
  created and a repair issue was raised.
- The run poll no longer fails once a workspace has a full page of completed
  jobs and at least one running job. It applied the same wrong row bound, so
  every refresh would have ended in a protocol error.
- Running and queued job counts are no longer inflated on a busy workspace.
  Windmill ignores the offset of `jobs/list`, so a later page can repeat an
  earlier one; observed jobs are now deduplicated by ID before they are counted.

### Changed

- The run poll requests smaller pages (30 instead of 100 completed rows) so a
  full page plus a plausible queue stays inside the client's response-size cap,
  and it treats a page as short when its *completed* rows are fewer than
  requested.

## [0.1.2] - 2026-08-03

### Changed

- Plain `http://` base URLs are accepted for any host. Previously HTTP was
  allowed only for loopback addresses, which rejected the common self-hosted
  setup — a Windmill instance on the LAN behind a local DNS name and no
  certificate, such as `http://windmill.home.arpa:8000`. A LAN hostname cannot
  be told apart from a public one when the config flow validates it, so the
  rule could not be narrowed; it was replaced by a visible warning instead.
- The config flow no longer states that HTTP is restricted to loopback.

### Added

- A repair issue whenever the configured base URL uses HTTP on a non-loopback
  host, stating that the Windmill token and all job payloads are transmitted
  unencrypted. Loopback raises no issue, and the issue disappears once the
  entry is reconfigured to `https://`.

### Security

- TLS verification for HTTPS connections is unchanged, and every other base-URL
  rule still applies: no embedded credentials, no query or fragment, no unsafe
  path segments.

## [0.1.1] - 2026-08-03

### Fixed

- Release automation targets the repository's actual default branch. The
  workflows still named `main` after the branch was renamed to `master`, so the
  tag verification in the release workflow could no longer resolve its
  reference and the push-triggered workflows stopped running.

### Note

- `0.1.0` is not installable. Its GitHub release carries no `windmill.zip`
  asset, so HACS reports a 404 for
  `releases/download/v0.1.0/windmill.zip`. The tag cannot be removed, so `0.1.1`
  supersedes it. There is no functional difference between the two versions
  beyond the release automation fix.

## [0.1.0] - 2026-08-02

### Added

- Initial release of the Windmill custom integration.
- Guided UI onboarding: connection and credential validation, workspace
  selection, capability explanation and opt-in feature selection, plus
  reauthentication, reconfigure and options flows.
- Capability negotiation with a five-state matrix and read-only bounded probes;
  features degrade gracefully when token permissions are missing.
- Instance health sensors, optional detailed health, and worker/worker-group
  observability.
- Run observability with a configurable scope (all visible jobs, selected
  runnables, or Home Assistant-started jobs), aggregate counters and a run
  event entity for automations, including exactly-once completion publication
  across restarts and reloads.
- Explicit discovery and selection of runnable scripts and flows; execution
  and cancellation of selected runnables via actions and button entities.
- Read-only update visibility when the deployment is eligible.
- Redacted diagnostics, actionable repair issues and rate-limit backoff.
- English and German translations with CI-enforced key parity.
- User documentation: installation, permission matrix, entities, actions,
  worker lifecycle, removal, troubleshooting, supported versions and known
  limitations.
- HACS packaging: `hacs.json`, brand assets, MIT license, HACS and hassfest
  validation in CI, and a tag-driven draft-release workflow producing a
  byte-reproducible `windmill.zip`.
