# 2026-08-03 — A guardrail that checks for a heading teaches agents to write headings

- Ticket: WMHA-0034
- Related ADR/research: `docs/architecture/decisions/0003-polling-remains-observation-mechanism.md`, `docs/research/windmill-push-observation.md`
- Publishable: yes

## Initial hypothesis

The repository requires an independent review for medium- and high-risk work, and a structural
validator enforces that every ticket carries a `## Review evidence` section. The expectation was
that the two rules together make an unreviewed medium-risk ticket hard to close.

## What happened

Two medium-risk tickets reached `tickets/done/` with all three bullets of that section reading
"pending independent review". Every automated check in the repository passed, because the check
tested for the presence of the heading, not for the presence of a result. The placeholder was even
prescribed by one of the tickets' own implementation plans, so the agent wrote it deliberately and
the validator confirmed the ticket was well-formed.

The failure is not that the rule was ignored. The rule was followed structurally and voided
semantically. A section whose only requirement is to exist gets filled with whatever satisfies
existence.

A second, smaller version of the same effect: the commit that closed one of the tickets ends its
message with "Independent review approved", while the ticket in that very commit says the review is
pending. Nothing checked the two against each other.

## Evidence

- `scripts/validate_repository.py` before this ticket: `REQUIRED_TICKET_SECTIONS` membership test
  only (`"## Review evidence" in text`).
- Both tickets passed `python scripts/validate_repository.py` at close time, recorded in their own
  validation tables.
- The eventual review, performed a day later, upheld both tickets' conclusions but found five
  defects, one of them a durable document asserting client behavior that a later fix had already
  changed. None of the five would have been found by any existing check.

## Decision or correction

The validator now requires a done ticket's review section to be non-empty and free of
`pending`/`TBD`/`TODO`. Both failure branches were proven to fail before the change was kept — an
empty section and a placeholder section each produce a distinct error.

The two historical tickets are named in an explicit grandfather set rather than edited, because
`tickets/done/` is append-only in this repository; a separate ticket carries their correction
record. The comment on that set says not to extend it, which is a weaker guarantee than code, and
is the honest state of it.

## Reusable lesson

When a process rule is enforced by a structural check, ask what the cheapest passing artifact looks
like. If the cheapest passing artifact is a heading with a placeholder under it, that is what an
agent under time pressure will produce — and it will produce it while believing it complied,
because the validator says so. Checks on required sections should assert something about the
content, even something as crude as "no unfinished-work words".

The corollary for reviews: "pending" is not a recorded deviation. Several earlier tickets in this
repository skipped the independent review too, but each wrote down that it had skipped it and why.
Those are auditable. "Pending" describes an intention, passes every check, and is indistinguishable
from a step that was simply never done.

## Limits

The new check catches a placeholder, not a bad review. A ticket whose review section says "reviewed,
no findings" without a review having happened passes exactly as before. Only the cheapest evasion
got more expensive; the honest-reporting requirement is still carried by the agent contract, not by
the validator.

## Redaction checklist

- [x] No secrets or tokens
- [x] No private hostnames or topology
- [x] No personal or production payloads
- [x] Version-sensitive claims include dates and sources
