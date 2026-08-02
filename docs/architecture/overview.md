# Architecture overview

This document describes the intended boundaries. Exact endpoints and data models remain subject to `WMHA-0001` research and an accepted ADR.

## Proposed components

```text
Home Assistant config flow / options flow
                 |
                 v
        Windmill API client
                 |
                 v
      Windmill HTTP API / webhooks

Home Assistant actions ---> application service ---> API client
Home Assistant entities <--- coordinator/cache <--- job status
```

## Boundaries

### Transport client

A Home Assistant-independent asynchronous client owns URL construction, authentication headers, timeouts, response parsing and typed domain errors. It must be testable with mocked HTTP responses and must never log secrets.

### Home Assistant adapter

Config flow, config-entry lifecycle, actions, coordinators and entities translate between Home Assistant concepts and the transport client. They must not reconstruct Windmill URLs independently.

### Configuration

Credentials and immutable connection identity belong in config-entry data. User-adjustable behavior belongs in options. Runnable exposure must be explicit rather than workspace-wide by default.

### Job observation

Asynchronous execution is the default. The first implementation should use the simplest verified bounded mechanism for status retrieval. Webhook callbacks or SSE are later options only if they improve reliability without requiring unsafe network exposure.

### Entity lifecycle

Entity sets are built when a config entry is set up and change only on reload. Volatile Windmill
objects are reflected in entity *state*, never in entity *existence*, so restarts and scaling do not
churn the entity registry. [ADR-0002](decisions/0002-worker-entity-lifecycle.md) records this for
worker groups and worker instances, including which workspace-side changes need a manual reload.

### Data minimization

Entity state and diagnostics must contain only metadata needed for operation. Arbitrary arguments, full results, authorization material and sensitive logs are excluded by default.

## Quality target

The custom integration should adopt current Home Assistant Bronze quality practices from its first usable release and make error recovery, reauthentication and diagnostics compatible with a later Silver target.
