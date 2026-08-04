# Home Assistant Windmill.dev Integration

A custom Home Assistant integration for observing a Windmill instance and running explicitly
selected Windmill scripts and flows.

The integration connects one config entry to one Windmill instance and workspace. It exposes
health, worker and run monitoring as entities, and starts or cancels jobs through Home Assistant
actions. It never imports a whole workspace: only scripts and flows you select in the options are
ever exposed.

## Features

**Monitor your instance**
- Instance status (`healthy` / `degraded` / `unhealthy`), database connectivity and active worker
  count — on by default.
- Pending and running job counts from the detailed health endpoint, for tokens with
  administrative access.
- Per-worker-group alive workers and version drift, plus optional per-worker-instance sensors for
  self-hosted operators.
- An update entity for self-hosted instances: installed version, latest version and release notes.

**Watch your runs**
- Running and queued top-level jobs in the workspace, plus timestamps of the last successful and
  last failed run.
- A `Run` event entity firing `success`, `failure` and `canceled` — the natural trigger for Home
  Assistant automations, with `job_id`, `path` and `duration_ms` as attributes.
- Choose the observation scope: every visible job, only your selected runnables, or only jobs Home
  Assistant started itself.
- Optional per-runnable devices with last run, last status, last duration, next scheduled run and
  a `Running` binary sensor — so even a script that last ran days ago still answers.

**Trigger scripts and flows**
- `windmill.run` starts a selected script or flow asynchronously and returns its job ID.
  Arguments are validated against the runnable's input schema before any request leaves Home
  Assistant.
- `windmill.cancel` cancels a queued or running job that Home Assistant started.
- Optional one-press buttons for selected runnables that need no arguments.
- Runnables can be pinned to a script hash or flow version, or follow the latest deployment.

**Built to be trustworthy**
- Explicit allow-list: at most 25 scripts and flows you pick yourself. No workspace import, and
  nothing runs that you did not select.
- Least-privilege tokens, sent only in an authorization header — never in URLs, logs, entity
  state or diagnostics, which are redacted before download.
- Guided config flow with capability detection: it reports what your instance, edition and token
  actually support instead of guessing. Execution is never probed during setup.
- Missing permissions or unsupported endpoints degrade one feature and raise a self-clearing
  repair issue; the rest of the entry keeps working.
- Fully asynchronous polling with automatic backoff on rate limits and server errors.
- Reauthentication and reconfiguration without deleting the entry, multiple instances and
  workspaces side by side, English and German UI.

## Installation

Requires Home Assistant 2026.7.0 or newer.

### HACS (recommended)

The integration is available through [HACS](https://www.hacs.xyz/) as a custom repository:

1. In Home Assistant, open **HACS → Integrations**, open the three-dot menu in the top right
   and choose **Custom repositories**.
2. Add `https://github.com/dprinz/ha-windmill-dev` with the category **Integration**.
3. Search for **Windmill** in HACS and download it.
4. Restart Home Assistant.
5. Go to **Settings → Devices & services → Add integration** and search for **Windmill**.

### Manual

1. Copy the `custom_components/windmill` directory of this repository into the
   `custom_components` directory of your Home Assistant configuration (or unpack the
   `windmill.zip` asset of a release into that directory).
2. Restart Home Assistant.
3. Go to **Settings → Devices & services → Add integration** and search for **Windmill**.

## Required Windmill permissions

The integration is built for least-privilege user tokens. The token is only ever sent in an
authorization header — never in URLs, logs, entity state or diagnostics.

| Capability | Windmill access needed | Needed for |
| --- | --- | --- |
| Sign-in and connection | `users:read` scope; membership of the workspace | Always required |
| Workspace list | `workspaces:read` scope (optional) | Picking the workspace from a list during setup; without it you type the workspace ID |
| Instance health | Token accepted on the instance health endpoint | `instance_health` feature (on by default) |
| Detailed health | Administrative token accepted on the detailed health endpoint | `detailed_health` feature (opt-in) |
| Workers | Administrative token accepted on the worker list endpoint | `worker_groups` and `worker_details` features (opt-in) |
| Runs | Read access to the workspace job list | `run_observation` feature (on by default) |
| Script and flow discovery | Read access to workspace scripts and flows | Selecting runnables in the options |
| Execution and cancellation | Permission to run the selected script or flow and to cancel jobs started by this token's user | `windmill.run`, `windmill.cancel` and runnable buttons |
| Update visibility | Token accepted on the update check endpoint; self-hosted only | `update_entity` feature (opt-in) |

Basic usage — health, run observation and running selected scripts or flows — works with a normal
workspace token. Administrative monitoring (detailed health, worker groups, worker details) is
additive and stays disabled until you opt in. Exact scope names beyond `users:read` and
`workspaces:read` depend on your Windmill edition and version; the setup flow reports what it
detected instead of guessing.

If a permission is missing, only the affected feature is unavailable — everything else loads
normally. For enabled features whose permission is denied, the integration creates a repair issue
that disappears on its own once the permission works.

## Configuration

Setup is a guided flow with progressive disclosure:

1. **Connect**: enter the base URL (for example `https://app.windmill.dev` or the URL of your
   self-hosted instance) and a token. Plain `http://` is accepted for self-hosted instances
   without a certificate; a repair issue then reminds you that the token travels unencrypted.
2. **Workspace**: pick the workspace, or type its ID when the token cannot list workspaces.
3. **Detected capabilities**: the flow shows what the instance, edition and token support.
   `unauthorized` means the token lacks a permission; `unsupported` means the deployment does not
   offer the endpoint. Execution is never probed during setup, because that would start a job.
4. **Features**: enable only what you need.

Feature options and their defaults:

| Option | Default | What it adds |
| --- | --- | --- |
| `instance_health` | on | Instance status enum sensor, database connectivity, active worker count |
| `detailed_health` | off | Pending and running job counts (administrative) |
| `worker_groups` | off | Per-group alive workers and version drift sensors (administrative) |
| `worker_details` | off | One sensor per worker instance (high cardinality, self-hosted operators) |
| `run_observation` | on | Workspace run counts, last-run timestamps and the run event entity |
| `update_entity` | off | Update entity for self-hosted instances |
| `runnable_buttons` | off | One button per selected parameterless runnable |
| `runnable_details` | off | One device per selected runnable with its last run, status, duration and next run |

The features step also offers the run observation scope (`run_scope`, default `all`). It decides
which top-level jobs the run sensors and the run event entity cover: `all` keeps every visible
top-level job, `selected_runnables` narrows observation to the scripts and flows selected under
**Configure → Scripts and flows**, and `home_assistant_started` narrows it to jobs this
integration started. Changing the scope never replays older completions as new events; the
last-run timestamps restart for the new scope while the replay protection is kept. One deliberate
interaction: a job cancelled through the integration's own cancel action emits no `canceled` event
under the `home_assistant_started` scope, because the cancel action stops tracking the job
immediately and the scope then no longer matches it — you cancelled the job yourself, so no event
is emitted. Under the `all` scope the cancellation fires normally.

Under **Configure → Scripts and flows** you select which scripts and flows Home Assistant may ever
run (at most 25). Optionally, newly selected runnables are pinned to their current script hash or
flow version; unpinned runnables follow the latest deployment. Changing options reloads the
integration automatically.

Multiple instance/workspace combinations can be configured; exact duplicates are rejected.
Reauthentication (new token) and reconfiguration (new URL or workspace) are available on the
config entry without deleting it.

## Entities

Entities belong to one service device per config entry. The only exception is
`runnable_details`, which gives every selected script and flow its own device below that one.
Names below are the English display names; German translations are included.

### Instance health (`instance_health`, on by default)

| Entity | Description |
| --- | --- |
| `Instance status` | Enum sensor: `healthy`, `degraded` or `unhealthy` |
| `Database` | Connectivity binary sensor: Windmill can reach its database |
| `Active workers` | Diagnostic sensor: workers that pinged recently |

### Detailed health (`detailed_health`, opt-in, administrative)

| Entity | Description |
| --- | --- |
| `Pending jobs` | Diagnostic sensor: queued jobs waiting for a worker |
| `Running jobs` | Diagnostic sensor: jobs currently running |

### Worker groups (`worker_groups`, opt-in, administrative)

One pair per worker group `<group>`:

| Entity | Description |
| --- | --- |
| `<group> active workers` | Diagnostic sensor: alive workers of the group |
| `<group> worker versions` | Diagnostic sensor: distinct Windmill versions in the group; above `1` means version drift |

### Worker details (`worker_details`, opt-in, high cardinality)

| Entity | Description |
| --- | --- |
| `Workers on <instance>` | Diagnostic sensor per worker instance: worker processes currently reporting |

### Run observation (`run_observation`, on by default)

| Entity | Description |
| --- | --- |
| `Running jobs in workspace` | Sensor: observed top-level jobs currently running |
| `Queued jobs in workspace` | Sensor: observed top-level jobs waiting to start |
| `Last successful run` | Timestamp sensor: last observed successful completion |
| `Last failed run` | Timestamp sensor: last observed failed completion |
| `Run` | Event entity with event types `success`, `failure` and `canceled` |

### Job details per runnable (`runnable_details`, opt-in)

Every script and flow you selected under **Configure → Scripts and flows** becomes its own device
below the workspace device, carrying five entities:

| Entity | Description |
| --- | --- |
| `Last run` | Timestamp sensor: when this runnable's last run finished |
| `Last status` | Enum sensor: `success`, `failure` or `canceled` |
| `Last duration` | Duration sensor: how long the last run took |
| `Next scheduled run` | Timestamp sensor: when a Windmill schedule will run this runnable next |
| `Running` | Binary sensor: whether a job of this runnable is executing right now |

Unlike the workspace-wide run observation, these entities answer for one runnable in particular,
including one that last ran days ago. They are filled from two sources: one request per selected
runnable every five minutes, and the shared run window that already refreshes every minute — so a
completion normally shows up within a minute, and the exact read is what keeps a rarely used job
from reporting nothing.

`Next scheduled run` is read from the job Windmill itself reserves in its queue for the next occurrence of a
schedule — the integration never reads or writes schedules, and never evaluates a cron expression.
A runnable without a schedule reports nothing, and disabling or deleting the schedule in Windmill
clears the value within one refresh.

The last known history survives a restart. `Running` and `Next scheduled run` deliberately do not: both
describe what Windmill is doing right now, and a restart is exactly when a restored value would
start claiming a run that finished or a schedule that was turned off in the meantime.

Deselecting a runnable removes its device, its entities and its stored history on the next reload.

### Runnable buttons (`runnable_buttons`, opt-in)

One `Run <path>` button per selected runnable that needs no arguments. Pressing a button starts
the runnable exactly like the `windmill.run` action and tracks the job for cancellation.

### Update (`update_entity`, opt-in, self-hosted only)

| Entity | Description |
| --- | --- |
| `Windmill server` | Read-only update entity: installed version, latest version and release notes link |

## Actions

### `windmill.run`

Starts a selected script or flow asynchronously and returns the Windmill job ID. Arguments are
validated against the runnable's input schema before any request is sent.

```yaml
action: windmill.run
data:
  config_entry_id: <your-config-entry-id>
  kind: script
  path: u/example/daily_cleanup
  arguments:
    room: kitchen
response_variable: result
```

`result.job_id` holds the job identifier. `config_entry_id` accepts the config-entry selector in
the UI automation editor, so you do not have to look the ID up manually.

### `windmill.cancel`

Cancels a queued or running job that Home Assistant started and still tracks (up to 50 jobs,
kept for 24 hours). Jobs started elsewhere in Windmill cannot be cancelled here.

```yaml
action: windmill.cancel
data:
  config_entry_id: <your-config-entry-id>
  job_id: "{{ result.job_id }}"
```

## Run events

The `Run` event entity fires once per newly observed completion. Event attributes are `job_id`,
`job_kind`, `path`, `duration_ms` and `started_by_home_assistant`. A typical automation:

```yaml
triggers:
  - trigger: state
    entity_id: event.example_workspace_run
    attribute: event_type
    to: failure
conditions:
  - condition: template
    value_template: "{{ trigger.to_state.attributes.path == 'u/example/daily_cleanup' }}"
actions:
  - action: notify.notify
    data:
      message: "Windmill job {{ trigger.to_state.attributes.job_id }} failed."
```

The entity ID derives from your config-entry title; the one above is an example. Completions are
observed by polling, so an event fires within roughly one poll interval (60 seconds), not in real
time. Completions that finish while the integration is down are observed by the refresh during
setup and fire once the event entity exists — on a Home Assistant start not before startup has
completed, so automations should be listening by then. A first-ever setup never replays history.

## Worker entity lifecycle

Worker entities are intentionally stable; they are built once when the config entry is set up and
change only when the entry is reloaded (see `docs/architecture/decisions/0002-worker-entity-lifecycle.md`):

- **A worker group or instance created in Windmill after setup gets no entity until you reload
  the integration** (config entry menu → *Reload*, or a Home Assistant restart). Option changes
  reload automatically; only workspace-side changes need a manual reload.
- **A worker that stops reporting keeps its entity and reports `0` instead of disappearing.** A
  silent worker is exactly the condition you want to alert on, and a deleted entity cannot be
  alerted on. Configured groups with no alive worker also report `0`.
- **Ephemeral instance identifiers are a known risk.** The per-instance entities of
  `worker_details` require `worker_instance` to stay stable across worker restarts. If your
  deployment derives it from a per-container hostname, every restart produces a new identifier and
  each reload adds another permanently-zero entity that you must delete manually. This is why the
  feature is opt-in and off by default.

## Cloud, self-hosted and permission-dependent behavior

- **Windmill Cloud** (`app.windmill.dev`): updated by Windmill, so the update entity is never
  created there even when `update_entity` is enabled. Everything else works when the token has
  the matching permission.
- **Self-hosted**: all features are available in principle, including the update entity. Older
  servers may not offer newer endpoints; the capability screen and repair issues say which
  feature is `unsupported` until you upgrade.
- **Permission-dependent**: administrative endpoints (detailed health, workers) depend on what
  your token and role may access, on any edition. An enabled feature whose permission is missing
  creates a repair issue instead of failing the whole entry.

## Supported versions and known limitations

The evidence-based compatibility statement — tested Home Assistant and Windmill versions, edition
behavior, live-smoke coverage and the accepted limitations of v1 — lives in
`docs/product/supported-versions-and-limitations.md`. Read it before upgrading Windmill or
reporting a compatibility issue.

## Removing the integration

1. Remove the config entry under **Settings → Devices & services → Windmill**. This also deletes
   the data the entry persisted locally (run-observation state and the started-job registry).
2. Revoke the token in Windmill. Home Assistant cannot revoke it for you, and the token stays
   valid until you do.

Note: stores orphaned by add-and-remove cycles from before this cleanup existed are not removed
retroactively. They are small, are never read again, and can be deleted manually from the
`.storage` directory (`windmill.runs.*` and `windmill.jobs.*` files whose entry ID no longer
exists) if you want them gone.

## Troubleshooting

**Authentication**
- `The token is invalid` or a reauthentication prompt: the token was revoked or expired. Create a
  new token in Windmill and use *Reauthenticate* on the config entry.
- `The token cannot access this workspace`: the token is valid but not a member of (or not
  accepted in) the configured workspace.

**TLS and connectivity**
- HTTPS is recommended. Plain HTTP is accepted for any host, because a self-hosted instance on
  the LAN often has no certificate and a hostname cannot be classified as local at validation
  time. Whenever the base URL is HTTP on a non-loopback host, the integration raises a repair
  issue: the token and every job payload travel unencrypted. TLS verification for HTTPS is never
  weakened — fix the certificate rather than falling back to HTTP.
- `Cannot connect to Windmill`: check the URL, DNS and that Home Assistant can reach the
  instance. Home Assistant System Health shows reachability per configured entry without exposing
  the token.

**Unsupported versions and permissions**
- A repair `Windmill does not support an enabled feature` means the server is older than the
  feature. Upgrade Windmill or turn the feature off in the options.
- A repair `Windmill permission missing for an enabled feature` means the token lacks a
  permission an enabled feature needs. Grant it in Windmill or disable the feature; the repair
  clears itself once fixed.
- A repair `Windmill worker group runs several versions` appears only when version drift lasts
  longer than 30 minutes, so rolling upgrades do not trigger it. Lasting drift usually means one
  worker failed to upgrade.

**Workers**
- A new group or instance has no entity: reload the integration (see *Worker entity lifecycle*).
- An entity reports `0`: the worker stopped reporting; check it in Windmill. The entity stays so
  your alert keeps working.
- Permanently-zero instances accumulating across reloads: your deployment uses ephemeral
  `worker_instance` identifiers; disable `worker_details` and delete the stale entities.

**Rate limits and temporary failures**
- `Windmill is temporarily unavailable`: Windmill returned a server error or asked the
  integration to slow down (HTTP 429). Polling backs off automatically (5 to 15 minutes) and
  recovers on its own; no repair issue is created for transient failures.

**Diagnostics**
- Use **Download diagnostics** on the device page. Tokens, job inputs, results and sensitive
  payload fields are redacted before anything leaves Home Assistant.

## Development

Work is repository-native and survives individual chat sessions:

1. `AGENTS.md` contains the stable operating contract for coding agents.
2. `tickets/` contains durable outcomes, acceptance criteria and scope boundaries.
3. `plans/` contains the mutable implementation approach for one ticket.
4. `docs/architecture/decisions/` contains decisions that must outlive a ticket.
5. `docs/blog/` captures publishable observations without turning the codebase into a diary.

Start with `AGENTS.md`, then `docs/context-map.md`.

Validation:

```bash
uv run pytest -q --cov=custom_components.windmill --cov-report=term-missing --cov-fail-under=95
uv run ruff check custom_components tests
uv run ruff format --check custom_components tests
uv run mypy custom_components/windmill
uv lock --check
python scripts/validate_repository.py
```
