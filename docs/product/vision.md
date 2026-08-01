# Product vision

## Problem

Home Assistant can call arbitrary HTTP endpoints, but generic REST calls do not provide a coherent Windmill user experience. Users must manually maintain URLs, payloads, authentication and job-state handling.

## Intended outcome

A user can add a Windmill instance through Home Assistant's UI, explicitly expose selected scripts or flows, trigger them through Home Assistant actions, and inspect meaningful execution state and failures.

## Product principles

- Safe by default: least privilege, no token leakage and no automatic import of an entire workspace.
- Home Assistant native: config entries, translations, repairs/reauth where appropriate and predictable actions/entities.
- Async first: no blocking network work in the event loop.
- Observable without becoming a log mirror: expose useful status, not arbitrary sensitive job output.
- Compatible with Windmill Cloud and self-hosted instances where the verified API contract permits it.
- Incremental: ship a narrow reliable foundation before advanced discovery, callbacks or streaming.

## Initial capability sequence

1. Verify the Windmill API and authentication contract.
2. Configure and validate one Windmill instance.
3. Trigger explicitly configured scripts and flows asynchronously.
4. Poll or subscribe to job completion using a bounded, efficient strategy.
5. Add selected status entities, events or actions based on validated user needs.

## Non-goals for the first release

- Managing or editing Windmill scripts and flows from Home Assistant.
- Mirroring all Windmill jobs, logs or results.
- Storing full arbitrary job results in Home Assistant state.
- Automatically granting access to every runnable in a workspace.
- Replacing Windmill's own scheduler, UI or authorization model.
