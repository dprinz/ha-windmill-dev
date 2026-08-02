# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
