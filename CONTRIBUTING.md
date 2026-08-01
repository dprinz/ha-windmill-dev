# Contributing

All changes start from a repository ticket.

1. Select a ticket from `tickets/ready/` and move it to `tickets/in-progress/`.
2. Create a branch named `<ticket-id>-<short-description>`.
3. Add a plan under `plans/` for multi-file or non-trivial work.
4. Keep the pull request limited to one outcome.
5. Add tests with the implementation and record the exact commands in the ticket.
6. Request an independent review before completion when risk is medium or high.
7. Move the ticket to `tickets/done/` only after validation evidence is complete.

Architecture changes require an ADR. External or version-sensitive claims require a primary source and verification date in `docs/research/`.
