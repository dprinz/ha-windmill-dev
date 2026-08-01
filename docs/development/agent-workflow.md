# Agentic development workflow

The repository uses tickets as durable outcome contracts, but avoids using one large prompt as the entire development process.

## 1. Shape

Turn a request into a bounded ticket. Define the outcome, measurable acceptance criteria, non-goals, risk and required context. A ticket with unresolved material API assumptions stays in backlog or becomes a research ticket.

## 2. Research

Use a dedicated research pass for external, version-sensitive facts. Prefer primary sources and record verification dates. Research output should reduce uncertainty, not create speculative code.

## 3. Plan

Create `plans/<ticket-id>.md` for non-trivial work. The plan is deliberately mutable and contains file-level changes, tests, sequencing, risks and rollback. The ticket remains stable unless the human changes the desired outcome.

## 4. Implement

Move one ticket to in-progress. Implement small coherent changes and tests. Update the plan when code reality differs. Scope discoveries become backlog tickets unless they block the current acceptance criteria.

## 5. Validate

Run actual commands and preserve concise evidence. Distinguish passed, failed and not-run checks. Never infer success from code inspection alone.

## 6. Independent review

A fresh reviewer starts from the ticket and diff. This reduces confirmation bias and catches scope drift. Medium- and high-risk work cannot complete without review evidence.

## 7. Close and distill

Move the ticket to done only after acceptance and validation. Promote only durable knowledge:

- architecture decisions to ADRs
- verified external facts to research notes
- reusable public observations to blog notes

Discard transient reasoning and stale plan detail instead of accumulating it in global context.

## Human checkpoints

Explicit human approval is required before:

- adding a dependency with runtime or supply-chain impact
- changing public action/entity contracts
- weakening security or TLS behavior
- handling or storing arbitrary Windmill results
- introducing inbound network exposure
- publishing a release or merging a pull request
