# ADR-0001: Safe five-state capability negotiation

- Status: accepted
- Date: 2026-08-02
- Deciders: project owner through WMHA-0003, implementation and independent review
- Related tickets: WMHA-0001, WMHA-0003, WMHA-0004, WMHA-0005 through WMHA-0011
- Supersedes: none

## Context

Windmill capabilities vary by server version, deployment, token scope, workspace permission and
user role. Health and read endpoints can be probed safely, but proving execution or cancellation
would create or mutate a job. A missing optional permission must not prevent unrelated Home
Assistant features from loading, and later platforms need a stable result rather than duplicating
HTTP interpretation.

The pinned Windmill v1.775.2 contract establishes `401`, `403`, `404`, `429` and `5xx` semantics,
but it does not provide a safe universal introspection endpoint that proves target-specific write
authorization.

## Decision drivers

- Never mutate Windmill during setup or periodic capability discovery.
- Keep authentication failure distinct from an optional permission denial.
- Make partial support explicit and consumable without reconstructing transport behavior.
- Bound request fan-out, pagination, retained data and refresh frequency.
- Avoid inferring authorization from edition labels or read access alone.

## Considered options

1. One boolean such as `supported` per feature.
2. Fail config-entry setup when any planned endpoint is unavailable.
3. Exercise write endpoints with disposable jobs to prove permissions.
4. Use a five-state result for each capability and defer target-specific writes until an explicit
   user operation has the required context.

## Decision

Use one immutable capability matrix per config entry. Every field is `available`, `unauthorized`,
`unsupported`, `temporarily_unavailable` or `not_applicable`, with a bounded reason enum.

Capability discovery uses a fixed set of safe, bounded GET probes through the shared async client.
For authenticated probes, `401` invalidates authentication; `403` is local to the capability;
`404` means unsupported for that endpoint probe. Connection, timeout, rate-limit and server errors
are temporary. A malformed success response is unsupported/incompatible and its body is discarded.

A successful read prerequisite does not prove a write permission. Script execution, flow
execution and cancellation therefore remain `not_applicable` until an explicitly selected
runnable or a Home Assistant-started eligible job supplies target context. The later operation
must still map authorization failures directly. Script and flow discovery have separate fields,
so their read-only `unauthorized` or `unsupported` result is never presented as a write result.

One Home Assistant `DataUpdateCoordinator` owns the capability snapshot per config entry. It uses
a conservative six-hour interval and Home Assistant's config-entry shutdown lifecycle. No module
global stores runtime state.

`available` update visibility means only that the bounded update-check endpoint contract worked;
it does not by itself authorize creation of an update entity for a managed Cloud deployment.

## Consequences

### Positive

- Optional permissions degrade independently and predictably.
- Later entities, onboarding and actions consume one typed source of capability truth.
- Setup and refresh cannot execute or cancel user workloads.
- Fixed probes and page size one keep discovery cost and retained data bounded.

### Negative

- Write permission cannot be promised during initial setup.
- The matrix has more states and requires user-facing explanation in WMHA-0004.
- Cloud/self-host update eligibility needs separate evidence before WMHA-0011 exposes an entity.

### Risks and mitigations

- A read prerequisite may succeed while the later write fails — keep write state contextual and
  preserve operation-time authorization errors.
- Permissions may change after setup — refresh the shared matrix conservatively and allow later
  flows to request an explicit refresh.
- Optional probes may increase startup traffic — run a fixed concurrent set with page size one and
  no retries.

## Validation

- Mocked client tests cover all five states, safe public/authenticated headers, bounded pagination,
  partial failures, malformed responses and secret-bearing payload disposal.
- Config-entry tests cover first refresh, authentication/transport translation, reload and the
  real coordinator shutdown callback. Streaming tests prove delayed chunks are consumed through
  EOF and rejected as soon as the aggregate body exceeds the hard cap.
- A read-only instance check confirms public and protected endpoint behavior without credentials or
  mutation; the pinned source contract remains normative.

## Revisit when

- Windmill exposes a safe current-token capability/introspection endpoint.
- A supported endpoint can prove a target-specific write without creating or changing a job.
- Cloud deployments expose a stable machine-readable deployment-kind signal.
- Capability churn or API cost justifies changing the coordinator refresh strategy.
