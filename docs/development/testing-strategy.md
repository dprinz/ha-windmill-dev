# Testing strategy

Testing grows with the implementation, but every ticket must name the exact commands it adds or relies on.

## Current foundation

Run:

```bash
python scripts/validate_repository.py
```

This validates required context files, ticket frontmatter, state-directory consistency, duplicate IDs, local Markdown links and translation files (missing or orphaned keys of every file in `custom_components/windmill/translations/` against `strings.json`).

## Integration test layers

When production code is introduced:

1. API-client unit tests use sanitized HTTP fixtures and cover success, authentication failure, connection failure, timeout, malformed response and server error.
2. Config-flow tests cover successful setup, duplicate prevention, invalid authentication, unreachable instances, reauthentication and reconfiguration when implemented.
3. Config-entry lifecycle tests use Home Assistant public interfaces for setup, unload and reload.
4. Action and entity tests assert behavior through Home Assistant's service registry, state machine and registries rather than internal implementation details.
5. Regression tests reproduce a bug before the fix and fail when the fix is removed.

## Current integration commands

The test environment is locked for Python 3.14.2 or newer and Home Assistant 2026.7.4; `AGENTS.md`
("Toolchain and versions") holds the binding version table. Every command below runs through
`uv run` on purpose. A bare `python`/`python3` picks up whatever interpreter the machine provides
and reports failures that do not exist in this project — most visibly
`SyntaxError: multiple exception types must be parenthesized` on the Python 3.14 exception syntax in
`custom_components/windmill/coordinator.py`. Check `uv run python -VV` before trusting any
surprising failure.

```bash
uv sync --group dev --python 3.14
uv run pytest -q --cov=custom_components.windmill --cov-report=term-missing --cov-fail-under=95
uv run ruff check custom_components tests
uv run ruff format --check custom_components tests
uv run mypy custom_components/windmill
python scripts/validate_repository.py
```

The Home Assistant test harness is a development-only dependency. Production uses Home
Assistant's bundled `aiohttp` session and adds no runtime package.

## What CI enforces

`.github/workflows/checks.yml` ("Tests, lint and types") runs this exact command list on every
pull request and on every push to `main`, plus `uv lock --check` so a stale lockfile fails the
build. The interpreter is resolved by `uv` from `.python-version`; the job prints `uv run python -VV`
before the checks, so a wrong-interpreter failure is visible in the log instead of being
misdiagnosed. A local result is therefore reproducible on a clean checkout, and a green check on
`main` covers the test suite, the coverage threshold, lint, formatting and types — not only the
structural guardrails (WMHA-0031).

The other two workflows cover different ground: `repository-guardrails.yml` runs
`scripts/validate_repository.py`, and `validate-hacs.yml` runs HACS and hassfest validation. When a
ticket cites CI as evidence, it names the job, not just "CI".

## Test isolation

- No automated test calls a real Windmill or Home Assistant production instance.
- Tokens, hostnames and payloads are obviously fake and sanitized.
- Time, retries and polling are controlled so tests remain deterministic.
- Snapshot tests are used only for stable complex output, never as a substitute for specific behavioral assertions.

## Completion evidence

A ticket records the command, exit status and relevant result. A check that was not run is written as `not run` with the reason; it is never represented as passed by inference.
