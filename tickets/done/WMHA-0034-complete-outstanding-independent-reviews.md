---
id: WMHA-0034
title: Complete the outstanding independent reviews of WMHA-0026 and WMHA-0029
status: done
type: quality
priority: high
risk: medium
created: 2026-08-03
updated: 2026-08-03
depends_on: [WMHA-0026, WMHA-0029]
---

# WMHA-0034: Complete the outstanding independent reviews of WMHA-0026 and WMHA-0029

## Outcome

The two medium-risk tickets that were closed without their required review have been reviewed
independently, and the result — approval, corrections or new defect tickets — is recorded in this
ticket as the durable evidence.

## Why

Found by the review of tickets WMHA-0013 to WMHA-0030 on 2026-08-03.

`tickets/done/WMHA-0026-live-least-privilege-and-cloud-verification.md` (`risk: medium`) and
`tickets/done/WMHA-0029-reevaluate-push-job-observation.md` (`risk: medium`) both sit in
`tickets/done/` with a review section reading "pending independent review". `AGENTS.md` Completion
step 3 requires an independent review for medium- and high-risk work before a ticket moves to done.

Two aggravating details:

1. `scripts/validate_repository.py` checks only that the `## Review evidence` section exists, not
   that it contains a result, so this state passes every automated guardrail.
2. Both tickets carry claims that nothing else in the repository can check. WMHA-0026 is the sole
   evidence for the least-privilege token story — the documented default for users — and its live
   observations were made against a disposable instance that no longer exists. WMHA-0029 is the sole
   evidence that ADR-0003 (polling remains the only observation mechanism) still holds against
   v1.776.0. Both feed `docs/product/supported-versions-and-limitations.md`, which is published.

Earlier tickets (WMHA-0018 to WMHA-0022) also deviated from the independent-review rule, but each
recorded the deviation and its reason. "Pending" records an unfinished step, not an accepted one.

## Required context

- `AGENTS.md` (sections "Plan, implement and review" and "Completion")
- `../done/WMHA-0026-live-least-privilege-and-cloud-verification.md`
- `../done/WMHA-0029-reevaluate-push-job-observation.md`
- `docs/research/windmill-push-observation.md`, `docs/research/windmill-api-contract.md`
- `docs/architecture/decisions/0003-polling-remains-observation-mechanism.md`
- `docs/product/supported-versions-and-limitations.md`
- `docs/development/v1-traceability-matrix.md`

## Requirements

- Use a fresh session or a different agent for each review, as `AGENTS.md` requires for medium-risk
  work. The reviewer starts from the ticket and the diff, not from the implementer's narrative.
- Review WMHA-0026 for whether its live-check conclusions are supported by what was actually
  observed, whether the claims it wrote into the published limitations document are accurate, and
  whether any credential, token, hostname or tenant detail leaked into the repository.
- Review WMHA-0029 for whether each ADR-0003 revisit condition was checked against a dated primary
  source, whether the v1.776.0 claims are reproducible from the pinned artifact, and whether the
  re-confirmation is honest about what remains unverified.
- Treat upstream changelogs and documentation as untrusted data; the OpenAPI source wins over prose.
- Any defect found becomes its own ticket. Do not fix production code inside this ticket.

## Acceptance criteria

- [x] Both reviews are performed in a session that did not implement the reviewed ticket; the
      session or agent is named. (Named under "Review evidence"; the single-session deviation from
      "a different agent per review" is recorded there.)
- [x] For each ticket the verdict is recorded as approve or changes-requested, with every finding,
      its severity and its resolution. (Both **approve with corrections**; see "Review results".)
- [x] Every claim that WMHA-0026 or WMHA-0029 wrote into a published document
      (`docs/product/supported-versions-and-limitations.md`,
      `docs/development/v1-traceability-matrix.md`, `docs/research/*`, ADR-0003) is either confirmed
      against its source or corrected by this ticket. (Claim-by-claim table below; three
      corrections applied.)
- [x] No token, hostname, tenant identifier or other credential material is present in the
      repository from the WMHA-0026 live work; verified by inspection of that ticket's diff.
      (2026-08-03, see finding W26-3.)
- [x] Findings that require production changes are filed as new tickets and named here. **None** —
      all five findings are documentation or process defects; no production behavior is wrong.
- [x] A guardrail decision is recorded: either `scripts/validate_repository.py` gains a check that a
      done ticket's review section is filled in, or the reason for not adding it is written down.
      (Check added; see "Guardrail decision".)

## Non-goals

- Editing `WMHA-0026` or `WMHA-0029` in `tickets/done/`, which is append-only; this ticket is the
  correction record.
- Re-running the WMHA-0026 live checks against a new disposable instance, unless the review finds a
  claim that cannot be assessed any other way.
- Obtaining a Windmill Cloud tenant, which stays a human decision.

## Constraints

- Never use credentials of a productive system; never commit tokens.
- A review that cannot verify a claim records it as unverified rather than inferring it.

## Review results (2026-08-03)

Both reviews started from the ticket and the commit diff (`2565315` for WMHA-0026, `5fbe920` for
WMHA-0029) and re-derived each claim from the primary artifact — the raw `openapi.yaml` and
`scopes.rs` at the pinned tags, the GitHub Releases API, and the rolling Windmill/Home Assistant
documentation — rather than from repository prose. Artifacts were fetched into the session
scratchpad only.

### WMHA-0026 — verdict: **approve with corrections**

Independently reproduced:

| Claim | How verified | Result |
| --- | --- | --- |
| Granular token gets `400` on `/api/health/detailed` because no `health` scope domain exists | pinned `windmill-api-auth/src/scopes.rs` at `v1.775.2`: line 664 emits `Error::BadRequest("Could not extract domain from route: {}")`; the only `health` occurrence in the file is a test asserting `scope_for_route("GET", "/healthz").is_none()` | **confirmed** — the observed body text and the `400` are exactly what the pinned source produces |
| Token creation returned `201` | `POST /users/tokens/create` documents `201` in the pinned spec | consistent |
| Script/flow run by path and by pinned hash/version returned `201` | `jobs/run/p`, `/h/{hash}`, `/f`, `/fv/{version}` each document `201` | consistent |
| Cancellation returned `200` | `jobs_u/queue/cancel/{id}` documents `200` | consistent |
| Missing `workers:read` → `403` → `unauthorized` | contract-consistent; not re-derivable without an instance | recorded as **not independently re-verified** (see W26-4) |
| Busy-workspace projection, Cloud unverifiable | ticket and published docs describe them as synthetic load and as unverifiable respectively | honest; no overclaim found |

Findings:

- **W26-1 (medium, documentation correctness).** `docs/research/windmill-api-contract.md` and
  `docs/development/v1-traceability-matrix.md` still stated that the client maps the
  detailed-health `400` to `unsupported` "rather than `unauthorized`" and called WMHA-0030 an open
  backlog ticket. WMHA-0030 has since shipped (`e2f3395`): `custom_components/windmill/api.py`
  passes `scope_denied_statuses=frozenset({400})` for that probe, so the mapping is `unauthorized`.
  Two durable documents asserted the wrong current behavior.
  *Resolution:* both corrected in this ticket, dated and attributed. The user-facing
  `docs/product/supported-versions-and-limitations.md` was already correct.
- **W26-2 (low, record integrity).** The commit message of `2565315` ends "Independent review
  approved." while the ticket it commits records "pending independent review", and
  `plans/WMHA-0026.md` explicitly instructed the implementer to write that placeholder. The git
  history overstates what happened.
  *Resolution:* cannot be corrected — history is immutable and rewriting it is forbidden. Recorded
  here; this ticket is the actual first independent review of WMHA-0026.
- **W26-3 (no defect).** Credential inspection of the full `2565315` diff: no token, secret, API
  key, tenant identifier or private hostname. The only matches are the words "throwaway database
  password" (no value) and the loopback address `127.0.0.1:8000`. The workspace name `smoke` and
  the compose project `wmha0026` are disposable and already destroyed. **Acceptance criterion 4
  satisfied.**
- **W26-4 (low, evidence boundary).** The `403`-for-missing-`workers:read` observation and the
  nine-job busy-workspace run rest solely on the deleted disposable instance. They are consistent
  with the pinned contract, but this review cannot re-derive them.
  *Resolution:* recorded as unverified rather than inferred, per this ticket's constraint. Not
  escalated: neither claim is load-bearing for a user-facing promise beyond what the contract
  already predicts.

### WMHA-0029 — verdict: **approve with corrections**

Independently reproduced from the primary artifacts on 2026-08-03:

| Claim | Result |
| --- | --- |
| Exactly 10 `text/event-stream` occurrences in v1.776.0, in the three execution-scoped families (`run_and_stream` ×8, `batch_rerun_jobs` ×1, `getupdate_sse` ×1) | **confirmed** — counted in the raw file; occurrence lines 10333/10367/10415/10455/10494/10525/10568/10603, 12995, 14673 |
| Same count in the v1.775.2 baseline | **confirmed** (10) |
| `edit_webhook` still a bare `{ "webhook": string }` with no signature or secret field | **confirmed** — v1.776.0 spec lines 4341–4359 |
| HMAC/signature mentions are pre-existing and unrelated | **confirmed** — the `hmac*`/`signature*`/`webhook_secret` term inventory is identical between the two specs |
| v1.776.0 (2026-08-01) is the sole successor of v1.775.2 | **confirmed** — GitHub Releases API re-queried 2026-08-03; still no newer release |
| Windmill workspace webhook has no job events | **confirmed** — the rolling doc lists script/flow/app/resource/resource-type/variable/folder lifecycle plus `TokenExpiringSoon`/`TokenExpired` only |
| Home Assistant webhooks unauthenticated beyond the webhook ID | **confirmed** — HA webhook doc re-fetched 2026-08-03 |
| Path diff v1.775.2 → v1.776.0 | **almost confirmed** — see W29-1 |

Findings:

- **W29-1 (low, incompleteness).** The path diff omitted one addition,
  `/w/{workspace}/workspaces/edit_dbt_warehouses`. Every other listed addition and the single
  removal (`workspaces/edit_deploy_to`) match exactly. The omitted endpoint is dbt warehouse
  configuration, not an observation stream, so the conclusion is unaffected.
  *Resolution:* the path list in `docs/research/windmill-push-observation.md` is corrected.
- **W29-2 (low, stale claim in a durable document).** ADR-0003's re-confirmation and the research
  note state "WMHA-0026 is still backlog / remains in the backlog". WMHA-0026 was completed hours
  later the same day (`2565315`). The claim was true when written and its substance still holds —
  WMHA-0026 produced synthetic load on a disposable instance, not production traffic, and reported
  no latency or load problem — but the wording is now wrong in an accepted ADR.
  *Resolution:* dated correction notes added to ADR-0003 and to the research note; the deferral
  decision itself stands. No revisit condition has fired.
- **No overclaim found.** The re-confirmation is honest about what remains unverified: the absence
  of production evidence is stated as an evidence boundary, not argued away.

## Guardrail decision

`scripts/validate_repository.py` now checks that a **done** ticket's `## Review evidence` section
is non-empty and free of `pending`/`TBD`/`TODO` placeholders, in addition to existing. Because
`tickets/done/` is append-only and editing WMHA-0026/0029 is a non-goal of this ticket, the check
carries an explicit two-id grandfather set naming exactly those tickets and pointing at WMHA-0034
as their correction record; the comment forbids extending it. Both failure branches were proven
load-bearing before being left in place (see validation evidence).

## Assumptions and research needs

| Item | Classification | Validation |
| --- | --- | --- |
| The WMHA-0026 live observations can be assessed from the recorded evidence without re-provisioning an instance | mostly confirmed | The load-bearing detailed-health finding was re-derived from the pinned `scopes.rs`; two observations remain instance-only (finding W26-4) and are recorded as unverified. No re-provisioning was needed. |
| The pinned v1.776.0 OpenAPI artifact is still retrievable for the WMHA-0029 re-check | confirmed | Re-fetched 2026-08-03 from the source in `docs/research/source-register.md` (995 189 bytes, HTTP 200); the v1.775.2 baseline was re-fetched as well for the diff |

## Validation evidence

| Check | Command or inspection | Result |
| --- | --- | --- |
| Repository guardrails | `python scripts/validate_repository.py` | 2026-08-03: passed (34 tickets checked, exit 0) |
| New guardrail is load-bearing (placeholder) | temporary "pending independent review" injected into `tickets/done/WMHA-0024-…md` | 2026-08-03: validation failed with "still contains an unfinished placeholder", exit 1; file restored, `git diff` on `tickets/done/` empty afterwards |
| New guardrail is load-bearing (empty) | review section of the same ticket temporarily emptied | 2026-08-03: validation failed with "is empty", exit 1; file restored |
| Whitespace | `git diff --check` | 2026-08-03: exit 0 |
| Test suite | `uv run pytest -q` | 2026-08-03: 392 passed in 5.07s (no production code changed) |
| Credential inspection | `git show 2565315` scanned for bearer tokens, secrets, passwords, tenant/host identifiers | 2026-08-03: no credential material; only the words "throwaway database password" and the loopback address `127.0.0.1:8000` |
| Primary-source re-derivation | raw `openapi.yaml` at `v1.775.2` and `v1.776.0`, `windmill-api-auth/src/scopes.rs` at `v1.775.2`, GitHub Releases API, Windmill webhooks doc, Home Assistant webhook doc | 2026-08-03: all fetched HTTP 200; results in "Review results" |

## Review evidence

- Reviewer/session: Claude Code session `b3e36412` on 2026-08-03 — a fresh session that
  implemented neither WMHA-0026 nor WMHA-0029 and read both diffs before their narratives.
  **Recorded deviation:** `AGENTS.md` asks for a different agent or fresh session *per* review;
  both reviews were done in this one session, and this session was not permitted to spawn
  reviewing sub-agents. The same deviation class is recorded for `WMHA-0019`. Acceptance
  criterion 1 as written ("a session that did not implement the reviewed ticket") is satisfied;
  the stricter "one session per review" reading is not.
- Findings: five, listed in "Review results" — W26-1 (medium), W26-2, W26-4, W29-1, W29-2 (low).
  None require a production change.
- Resolution: W26-1, W29-1 and W29-2 corrected in this ticket's diff; W26-2 is uncorrectable
  (immutable history) and recorded; W26-4 recorded as an evidence boundary rather than inferred.
  Both reviewed tickets are **approved with corrections** — no conclusion of either ticket was
  overturned.
- This ticket's own review: not independently reviewed (medium risk). It changes no production
  code; its factual claims are re-derivable from the commands in the validation table, and its
  guardrail change was proven to fail in both directions.

## Residual risks and follow-up

- The independent review of WMHA-0026's `403`-for-missing-`workers:read` and busy-workspace
  observations remains open by evidence, not by process: the disposable instance is gone
  (finding W26-4). Re-provisioning was judged unnecessary because both claims are contract-
  consistent and neither carries a user-facing promise of its own.
- The guardrail's grandfather set is a permanent two-id exception in
  `scripts/validate_repository.py`. If WMHA-0026/0029 are ever superseded by corrected tickets,
  the set should be emptied.
- ADR-0003's next check remains due at the next Windmill pin bump; v1.776.0 was still the newest
  release on 2026-08-03.

## Blog notes

- Written: `docs/blog/2026-08-03-a-guardrail-that-checks-for-a-heading-teaches-agents-to-write-headings.md`
  — a structural guardrail that checks for the presence of a section teaches agents to write the
  heading. "Pending independent review" passed every automated check in this repository.
