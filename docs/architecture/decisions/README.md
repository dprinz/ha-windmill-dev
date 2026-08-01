# Architecture decision records

Use an ADR for a decision that constrains multiple future tickets or would be costly to rediscover. Do not create ADRs for routine implementation choices.

## Lifecycle

- `proposed` — under discussion
- `accepted` — current decision
- `superseded` — replaced by a newer ADR
- `rejected` — considered but not adopted

Name files `NNNN-short-title.md`. Copy `0000-template.md`, assign the next number and link superseding decisions in both directions.

Accepted ADRs are durable constraints. A ticket plan may explain how to apply them but must not silently override them.
