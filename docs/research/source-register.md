# Source register

Version-sensitive implementation claims must be traced to primary sources. Re-check sources when a ticket depends on them and the verification date is stale.

| Area | Primary source | Last checked | Used for |
| --- | --- | --- | --- |
| GitHub repository and agent instructions | https://docs.github.com/en/copilot/reference/custom-instructions-support | 2026-08-01 | `AGENTS.md`, scoped instructions and adapter support |
| GitHub custom agents | https://docs.github.com/en/copilot/concepts/agents/cloud-agent/about-custom-agents | 2026-08-01 | `.github/agents/*.agent.md` format and role profiles |
| Home Assistant Integration Quality Scale | https://developers.home-assistant.io/docs/core/integration-quality-scale/ | 2026-08-01 | Bronze-first quality target |
| Home Assistant config flows | https://developers.home-assistant.io/docs/core/integration/config_flow/ | 2026-08-02 | UI setup, entry data, duplicate handling, unique-ID constraints and lifecycle |
| Home Assistant testing | https://developers.home-assistant.io/docs/development_testing/ | 2026-08-02 | pytest, public-interface testing and coverage strategy |
| Home Assistant integration structure | https://developers.home-assistant.io/docs/creating_integration_file_structure/ | 2026-08-01 | component layout |
| Windmill webhooks and job execution | https://www.windmill.dev/docs/core_concepts/webhooks | 2026-08-01 | async/sync execution, bearer auth and job IDs |
| Windmill user tokens | https://www.windmill.dev/docs/core_concepts/user_tokens | 2026-08-01 | least-privilege scopes and token handling |
| Windmill self-hosted health endpoints | https://www.windmill.dev/docs/advanced/self_host | 2026-08-01 | unauthenticated and authenticated health behavior |
| Windmill API v1.775.2 OpenAPI | https://github.com/windmill-labs/windmill/blob/v1.775.2/backend/windmill-api/openapi.yaml | 2026-08-01 | endpoint, parameter, pagination and response contracts |
| Windmill API v1.775.2 router/source | https://github.com/windmill-labs/windmill/blob/v1.775.2/backend/windmill-api/src/lib.rs | 2026-08-01 | route layering, version, edition and update behavior |
| Windmill API v1.775.2 health source | https://github.com/windmill-labs/windmill/blob/v1.775.2/backend/windmill-api/src/health.rs | 2026-08-01 | health caching, status calculation and authorization ambiguity |
| Windmill v1.775.2 release | https://github.com/windmill-labs/windmill/releases/tag/v1.775.2 | 2026-08-01 | immutable research baseline |
| Windmill jobs | https://www.windmill.dev/docs/core_concepts/jobs | 2026-08-01 | job lifecycle semantics |
| Windmill versioning | https://www.windmill.dev/docs/core_concepts/versioning | 2026-08-01 | script hashes and flow versions |
| Windmill worker groups | https://www.windmill.dev/docs/core_concepts/worker_groups | 2026-08-01 | worker-group and edition behavior |
| Windmill v1.775.2 scope middleware | https://github.com/windmill-labs/windmill/blob/v1.775.2/backend/windmill-api-auth/src/scopes.rs | 2026-08-01 | route-domain/action mapping and restricted-token enforcement |
| Windmill v1.775.2 worker handlers | https://github.com/windmill-labs/windmill/blob/v1.775.2/backend/windmill-api-workers/src/lib.rs | 2026-08-01 | worker visibility and DevOps-role checks |
| Windmill v1.775.2 config handlers | https://github.com/windmill-labs/windmill/blob/v1.775.2/backend/windmill-api-configs/src/lib.rs | 2026-08-01 | worker-group access and config obfuscation |
| Windmill v1.775.2 authentication extractor | https://github.com/windmill-labs/windmill/blob/v1.775.2/backend/windmill-api-auth/src/auth.rs | 2026-08-01 | route-scope checks applied to granular-scoped tokens |
| Home Assistant Core 2026.7.4 | https://github.com/home-assistant/core/releases/tag/2026.7.4 | 2026-08-02 | pinned implementation and test baseline |
| Home Assistant integration manifest | https://developers.home-assistant.io/docs/creating_integration_manifest/ | 2026-08-02 | custom integration metadata, version and config-flow declaration |
| Home Assistant integration setup failures | https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/test-before-setup/ | 2026-08-02 | setup retry and authentication failure mapping |
| pytest-homeassistant-custom-component 0.13.348 | https://pypi.org/project/pytest-homeassistant-custom-component/0.13.348/ | 2026-08-02 | test-only harness pinned to Home Assistant 2026.7.4 |
| HACS publishing requirements | https://www.hacs.xyz/docs/publish/start/ and https://www.hacs.xyz/docs/publish/integration/ | 2026-08-02 | `hacs.json` schema, repository layout, manifest keys, brand assets |
| HACS validation action | https://www.hacs.xyz/docs/publish/action/ and https://github.com/hacs/action | 2026-08-02 | CI validation workflow, pinning limits of the Docker action |
| HACS ZIP extraction behavior | https://github.com/hacs/integration/blob/main/custom_components/hacs/repositories/base.py | 2026-08-02 | release ZIP must contain integration files at its root |
| hassfest action | https://github.com/home-assistant/actions | 2026-08-02 | only `master` branch maintained; pinned by SHA |
| Windmill v1.775.2 OpenAPI SSE inventory | https://github.com/windmill-labs/windmill/blob/v1.775.2/backend/windmill-api/openapi.yaml | 2026-08-02 | per-job SSE endpoints only; no workspace-wide job event stream (WMHA-0016) |
| Windmill streaming | https://www.windmill.dev/docs/core_concepts/streaming | 2026-08-02 | result/AI streaming model, SSE consumption paths (WMHA-0016) |
| Windmill error handling | https://www.windmill.dev/docs/core_concepts/error_handling | 2026-08-02 | error/success handler contracts and edition gating (WMHA-0016) |
| Windmill workspace webhook event types | https://www.windmill.dev/docs/core_concepts/webhooks | 2026-08-02 | outbound webhook covers resource lifecycle only, no job events (WMHA-0016) |
| Home Assistant webhook trigger | https://www.home-assistant.io/integrations/webhook/ | 2026-08-02 | inbound reachability, secret-id auth model, `local_only` (WMHA-0016) |
| Windmill v1.776.0 release | https://github.com/windmill-labs/windmill/releases/tag/v1.776.0 | 2026-08-02 | sole successor of pinned v1.775.2; changelog spot check (WMHA-0029) |
| Windmill API v1.776.0 OpenAPI | https://github.com/windmill-labs/windmill/blob/v1.776.0/backend/windmill-api/openapi.yaml | 2026-08-02 | successor SSE inventory (10 occurrences, unchanged 3 families), webhook/signature search, path diff (WMHA-0029) |
| Windmill GitHub releases API | https://api.github.com/repos/windmill-labs/windmill/releases | 2026-08-02 | complete set of releases after the pin (WMHA-0029) |

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
