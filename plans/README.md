# Implementation plans

Plans are mutable execution documents linked one-to-one with non-trivial tickets. They are not requirements and do not outrank the ticket or accepted ADRs.

A useful plan contains:

- verified current state
- file-level changes
- acceptance-criterion mapping
- implementation sequence and checkpoints
- tests and validation commands
- failure modes, security concerns and rollback
- discoveries that require ticket or ADR changes

Create `plans/<ticket-id>.md` from `_template.md`. Delete a purely transient plan after completion only when all durable knowledge has been promoted and the ticket retains sufficient evidence; otherwise keep it for auditability.
