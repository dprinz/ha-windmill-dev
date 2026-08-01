# 2026-08-02 — Bounded streams need EOF and owned tasks

- Ticket: WMHA-0003
- Related ADR/research: `docs/architecture/decisions/0001-capability-negotiation.md`
- Publishable: yes

## Initial hypothesis

Reading at most the configured response limit plus one byte appeared sufficient to bound an HTTP
response. Running independent capability probes with `asyncio.gather` also appeared to give the
caller one failure boundary for the complete fan-out.

## What happened

Independent review found two gaps. A stream read may return fewer bytes before EOF, so one read can
accept a valid first chunk while leaving an oversized tail unread. In addition, a fast
authentication failure can leave slower sibling coroutines running unless their tasks are
explicitly cancelled and awaited before the error escapes.

## Evidence

`tests/test_api.py` supplies a valid first response chunk followed by an oversized delayed tail and
asserts that the aggregate hard limit rejects it. `tests/test_capabilities.py` forces a fast
authentication failure beside a slow probe and asserts that the sibling observes cancellation
before capability discovery returns.

## Decision or correction

The transport now reads repeatedly through EOF while enforcing the aggregate byte limit after each
chunk. Capability discovery creates and owns every probe task; on any escaping failure it cancels
all tasks, awaits them with exception collection enabled and only then re-raises the original
failure.

## Reusable lesson

A maximum argument to an asynchronous stream read limits one read, not the complete response.
Likewise, concurrent work is not lifecycle-safe merely because it was passed to a gathering
primitive: the boundary that starts tasks must also guarantee their cleanup on every exit path.

## Limits

The tests establish the integration's bounded-reader and cancellation behavior in the pinned test
environment. They do not characterize every upstream server's chunk timing or prove that future
probe implementations contain no independently spawned work.

## Redaction checklist

- [x] No secrets or tokens
- [x] No private hostnames or topology
- [x] No personal or production payloads
- [x] Version-sensitive claims include dates and sources
