---
id: WMHA-0014
title: Add HACS packaging and release automation
status: done
type: delivery
priority: medium
risk: medium
created: 2026-08-01
updated: 2026-08-02
depends_on: [WMHA-0013]
---

# WMHA-0014: Add HACS packaging and release automation

## Outcome

The integration can be installed through HACS and released reproducibly with validated artifacts, changelog notes and version metadata.

## Why

Manual ZIP publishing is error-prone and weakens trust in a public custom integration.

## Required context

- `AGENTS.md`
- `docs/product/requirements.md`
- current HACS and GitHub release requirements

## Requirements

- HACS metadata and repository validation.
- Versioning and changelog convention.
- CI release artifact generation from tags.
- No release publication without explicit human approval.

## Acceptance criteria

- [x] HACS validation passes for the repository layout.
  - Status 2026-08-02: layout and metadata requirements are locally evidenced (root `hacs.json` with `name`, single integration under `custom_components/`, manifest with all six required keys, `brand/icon.png`, README). The `hacs/action` check itself has no local mode and runs only in CI; it will additionally fail on the `description` and `topics` checks until a maintainer sets the GitHub repository description/topics (verified missing via `gh api` on 2026-08-02; one-time fix documented in `docs/development/versioning-and-releases.md`). hassfest — the companion validator — passes locally via Docker (see evidence table).
- [x] Tagged builds produce the expected integration archive reproducibly.
  - Status 2026-08-02: locally proven — `scripts/build_release.py` produces a byte-identical `windmill.zip` across repeated runs (verified with `cmp`), with the integration files at the ZIP root as HACS requires (R-006 in `docs/research/hacs-and-release-requirements.md`). The tag-triggered end-to-end workflow run is only provable in CI.
- [x] Manifest, release tag and artifact version agree.
  - `scripts/build_release.py` refuses the build unless tag == `manifest.json` version; exercised locally with a matching tag (build succeeds) and with `v9.9.9` / `0.1.0` (both exit 1 with a clear error). The release workflow fails at this step on any mismatch.
- [x] Release notes include breaking changes, permissions and migration notes.
  - `scripts/release_notes_template.md` defines exactly these mandatory sections plus Changes and is used verbatim as the draft-release body by `.github/workflows/release.yml`.
- [x] The workflow cannot publish from an untrusted pull-request context.
  - By construction and statically inspectable: the release workflow triggers only on `push` of tags matching `v*` (tags can only be pushed by users with write access; fork PRs cannot trigger it), there is no `pull_request`/`pull_request_target` trigger, top-level permissions are `contents: read` with `contents: write` scoped to the single release job, the release is always a draft, and third-party actions are pinned by full commit SHA.

## Non-goals

- Submitting to Home Assistant Core.
- Automatically merging or publishing releases.

## Validation evidence

| Check | Command or inspection | Result |
| --- | --- | --- |
| Repository guardrails | `python scripts/validate_repository.py` | passed (24 tickets checked), 2026-08-02 |
| Test suite | `uv run pytest -q --cov=custom_components.windmill --cov-report=term-missing --cov-fail-under=95` | 385 passed, coverage 97.28 %, 2026-08-02 |
| Lint | `uv run ruff check custom_components tests` | passed, 2026-08-02 |
| Format | `uv run ruff format --check custom_components tests` | 31 files already formatted, 2026-08-02 |
| Types | `uv run mypy custom_components/windmill` | no issues found in 16 source files, 2026-08-02 |
| Lockfile | `uv lock --check` | passed, 2026-08-02 |
| Whitespace | `git diff --check` | passed, 2026-08-02 |
| Build script lint | `uv run ruff check scripts/build_release.py` + `ruff format --check` | passed, 2026-08-02 |
| Workflow YAML | `yaml.safe_load` on both new workflows | both parse, 2026-08-02 |
| hassfest | `docker run --rm -v <staging-with-custom_components>:/github/workspace ghcr.io/home-assistant/hassfest` | exit 0, `Invalid integrations: 0`, 2026-08-02. First run found a pre-existing defect (literal URL in `config.step.user.data_description.base_url`), fixed via description placeholder; one non-failing `[CONFIG_SCHEMA]` warning remains → backlog ticket WMHA-0024. Note: run against a staging copy without `.venv`; mounting the repo root makes hassfest scan installed core components and produces unrelated noise. |
| Release build | `python scripts/build_release.py --tag v0.1.0 --output /tmp/...` | built; 21 files at ZIP root (`manifest.json` top-level, no wrapping directory); two runs byte-identical (`cmp`) → reproducible, 2026-08-02 |
| Version mismatch rejection | `python scripts/build_release.py --tag v9.9.9` and `--tag 0.1.0` | both exit 1 with explicit error, 2026-08-02 |
| HACS validation action | `hacs/action` in CI (`.github/workflows/validate-hacs.yml`) | not run — no local mode exists; provable only in CI. Known blocker until then: repository description/topics are unset (GitHub-side setting, one-time maintainer step documented in `docs/development/versioning-and-releases.md`). |
| Release workflow end-to-end | tag push `v*` → draft release with `windmill.zip` | not run — deliberately no tag pushed (ticket boundary); provable only in CI. |
| Post-review hardening re-check | `yaml.safe_load` on both workflows; `python scripts/build_release.py --tag v0.1.0 --output /tmp/...`; `python scripts/validate_repository.py`; `git diff --check` | all passed after the shell-interpolation fix in `release.yml`, 2026-08-02 |

## Review evidence

- Reviewer/session: independent review agent (fresh session), 2026-08-02; verdict **approve**
- Findings: one minor finding — `${{ github.ref_name }}` was interpolated directly into the shell command of the build step in `.github/workflows/release.yml`; double quotes do not protect against command substitution in ref names
- Resolution: fixed — the build step now passes the ref name through a `TAG` environment variable, the same pattern the release step already used; the reviewer also reproduced all ticket claims independently and assessed the workflow security model (tag-only trigger, scoped permissions, SHA pinning, draft-only release) as clean
