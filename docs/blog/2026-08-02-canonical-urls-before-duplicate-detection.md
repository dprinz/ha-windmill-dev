# 2026-08-02 — Canonicalize URLs before duplicate detection

- Ticket: WMHA-0002
- Related ADR/research: `docs/research/windmill-api-contract.md`
- Publishable: yes

## Initial hypothesis

Lowercasing the host, removing default ports and rejecting literal dot segments appeared
sufficient to derive a stable non-secret config-entry identity from a Windmill base URL.

## What happened

Independent review showed that an HTTP client can canonicalize percent-encoded path segments
after duplicate detection. For example, an encoded unreserved character can make two stored URLs
look different while both requests reach the same path. Encoded dot segments can also be resolved
by the transport before sending the request.

## Evidence

Regression tests in `tests/test_api.py` compare encoded and canonical paths and reject encoded
traversal. `tests/test_config_flow.py` proves that equivalent encoded deployment paths collide.
The focused review then compared the normalized result with aiohttp/yarl request behavior.

## Decision or correction

The integration strictly decodes each path segment, rejects traversal, encoded separators and
control characters, and encodes the accepted segment into one canonical representation before it
is stored or used as a duplicate key.

## Reusable lesson

A URL used as an identity must be canonicalized according to the same semantics as the transport.
Validation against only its source spelling is insufficient for security and duplicate detection.

## Limits

The tests cover the accepted deployment-path policy and aiohttp/yarl behavior in the pinned test
environment. They do not prove how every reverse proxy handles repeated or non-standard decoding.

## Redaction checklist

- [x] No secrets or tokens
- [x] No private hostnames or topology
- [x] No personal or production payloads
- [x] Version-sensitive claims include dates and sources
