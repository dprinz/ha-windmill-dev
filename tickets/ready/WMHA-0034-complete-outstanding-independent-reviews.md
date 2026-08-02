---
id: WMHA-0034
title: Complete the outstanding independent reviews of WMHA-0026 and WMHA-0029
status: ready
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

- [ ] Both reviews are performed in a session that did not implement the reviewed ticket; the
      session or agent is named.
- [ ] For each ticket the verdict is recorded as approve or changes-requested, with every finding,
      its severity and its resolution.
- [ ] Every claim that WMHA-0026 or WMHA-0029 wrote into a published document
      (`docs/product/supported-versions-and-limitations.md`,
      `docs/development/v1-traceability-matrix.md`, `docs/research/*`, ADR-0003) is either confirmed
      against its source or corrected by this ticket.
- [ ] No token, hostname, tenant identifier or other credential material is present in the
      repository from the WMHA-0026 live work; verified by inspection of that ticket's diff.
- [ ] Findings that require production changes are filed as new tickets and named here.
- [ ] A guardrail decision is recorded: either `scripts/validate_repository.py` gains a check that a
      done ticket's review section is filled in, or the reason for not adding it is written down.

## Non-goals

- Editing `WMHA-0026` or `WMHA-0029` in `tickets/done/`, which is append-only; this ticket is the
  correction record.
- Re-running the WMHA-0026 live checks against a new disposable instance, unless the review finds a
  claim that cannot be assessed any other way.
- Obtaining a Windmill Cloud tenant, which stays a human decision.

## Constraints

- Never use credentials of a productive system; never commit tokens.
- A review that cannot verify a claim records it as unverified rather than inferring it.

## Assumptions and research needs

| Item | Classification | Validation |
| --- | --- | --- |
| The WMHA-0026 live observations can be assessed from the recorded evidence without re-provisioning an instance | assumption | Confirm while reviewing; escalate if a claim rests only on the deleted instance |
| The pinned v1.776.0 OpenAPI artifact is still retrievable for the WMHA-0029 re-check | assumption | Re-fetch from the source named in `docs/research/source-register.md` |

## Validation evidence

Fill during implementation; do not pre-check.

| Check | Command or inspection | Result |
| --- | --- | --- |
| Repository guardrails | `python scripts/validate_repository.py` | not run |

## Review evidence

- Reviewer/session:
- Findings:
- Resolution:

## Residual risks and follow-up

- None recorded

## Blog notes

- Candidate: a structural guardrail that checks for the presence of a section teaches agents to
  write the heading. "Pending independent review" passed every automated check in this repository.
