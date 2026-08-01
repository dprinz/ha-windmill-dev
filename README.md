# Home Assistant Windmill.dev Integration

A custom Home Assistant integration for running and observing Windmill scripts and flows.

## Status

The repository currently contains the agentic development foundation. Production integration code has not been implemented yet.

## Product goal

The integration should let Home Assistant users configure a Windmill instance through the UI, trigger explicitly selected scripts and flows, and observe job state without exposing unnecessary Windmill permissions.

The first implementation target is a reliable HACS custom integration designed against the current Home Assistant Integration Quality Scale. A later contribution to Home Assistant Core remains possible, but is not assumed.

## Development model

Work is repository-native and survives individual chat sessions:

1. `AGENTS.md` contains the stable operating contract for coding agents.
2. `tickets/` contains durable outcomes, acceptance criteria and scope boundaries.
3. `plans/` contains the mutable implementation approach for one ticket.
4. `docs/architecture/decisions/` contains decisions that must outlive a ticket.
5. A separate reviewer evaluates the diff against the ticket and evidence.
6. `docs/blog/` captures publishable observations without turning the codebase into a diary.

Start with `AGENTS.md`, then select exactly one ticket from `tickets/ready/`.

## Repository map

- `custom_components/windmill/` — future Home Assistant integration
- `tests/` — future automated tests
- `tickets/` — repository-native work queue
- `plans/` — implementation plans linked to tickets
- `docs/` — product, architecture, research and development context
- `.github/agents/` — specialized GitHub Copilot agent profiles
- `.github/prompts/` — reusable task prompts
- `scripts/validate_repository.py` — lightweight repository guardrails

## Validate the foundation

```bash
python scripts/validate_repository.py
```
