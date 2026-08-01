# Source register

Version-sensitive implementation claims must be traced to primary sources. Re-check sources when a ticket depends on them and the verification date is stale.

| Area | Primary source | Last checked | Used for |
| --- | --- | --- | --- |
| GitHub repository and agent instructions | https://docs.github.com/en/copilot/reference/custom-instructions-support | 2026-08-01 | `AGENTS.md`, scoped instructions and adapter support |
| GitHub custom agents | https://docs.github.com/en/copilot/concepts/agents/cloud-agent/about-custom-agents | 2026-08-01 | `.github/agents/*.agent.md` format and role profiles |
| Home Assistant Integration Quality Scale | https://developers.home-assistant.io/docs/core/integration-quality-scale/ | 2026-08-01 | Bronze-first quality target |
| Home Assistant config flows | https://developers.home-assistant.io/docs/core/integration/config_flow/ | 2026-08-01 | UI configuration and config-entry lifecycle |
| Home Assistant testing | https://developers.home-assistant.io/docs/development_testing/ | 2026-08-01 | pytest, public-interface testing and coverage strategy |
| Home Assistant integration structure | https://developers.home-assistant.io/docs/creating_integration_file_structure/ | 2026-08-01 | component layout |
| Windmill webhooks and job execution | https://www.windmill.dev/docs/core_concepts/webhooks | 2026-08-01 | async/sync execution, bearer auth and job IDs |
| Windmill user tokens | https://www.windmill.dev/docs/core_concepts/user_tokens | 2026-08-01 | least-privilege scopes and token handling |
| Windmill self-hosted health endpoints | https://www.windmill.dev/docs/advanced/self_host | 2026-08-01 | unauthenticated and authenticated health behavior |

## Research note requirements

For each material claim record:

- exact claim
- source URL and relevant version/update date
- verification date
- direct evidence or endpoint/schema reference
- confidence: high, medium or low
- implications for implementation
- unresolved ambiguity

Documentation prose is not enough when an official OpenAPI schema or source implementation contradicts it.
