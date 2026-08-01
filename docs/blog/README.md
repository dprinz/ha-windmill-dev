# Development notes for later blog posts

This directory captures evidence-backed observations that may later become a blog article. It is not a chronological activity log and should not duplicate tickets.

Create a note only when at least one of these is true:

- an initial assumption was disproved
- a design trade-off produced a measurable result
- an agent workflow succeeded or failed in a reusable way
- a Home Assistant or Windmill edge case required non-obvious handling
- independent review found something the implementation session missed

Use `entry-template.md`. Link the ticket, plan, ADR, commit or test evidence. Clearly distinguish what was expected, what actually happened and what remains uncertain.

Before publication, remove private infrastructure details, secrets, personal data, internal URLs and unverified claims. The public article may discuss the method; it must not expose sensitive execution traces or credentials.
