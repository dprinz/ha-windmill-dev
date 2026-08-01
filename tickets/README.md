# Repository tickets

Tickets are versioned work contracts. They preserve intent across agent sessions and code changes.

## States

- `backlog/` — useful idea, but blocked, too vague or not yet prioritized
- `ready/` — actionable outcome with testable acceptance criteria and sufficient context
- `in-progress/` — actively owned; normally one per agent/worktree
- `done/` — accepted historical record with validation evidence

The directory and the ticket's `status` frontmatter must match.

## Ticket versus plan

The ticket states **what must become true** and what is out of scope. It should remain stable during implementation.

The matching file under `plans/` states **how the current agent intends to achieve it**. Plans may change as the repository is inspected. This separation prevents accidental rewriting of the requirement to fit the code.

## Readiness criteria

A ticket is ready only when it has:

- one bounded outcome
- measurable acceptance criteria
- explicit non-goals
- dependencies and risk level
- a minimal context manifest
- research tasks for unresolved external facts

## Completion criteria

A ticket is done only when:

- all acceptance criteria are checked against the final diff
- validation commands and actual results are recorded
- medium/high-risk work has independent review evidence
- residual risks and follow-up tickets are named
- durable decisions and research have been promoted to the appropriate docs

Copy `_templates/ticket.md` and use an ID in the form `WMHA-NNNN`.
