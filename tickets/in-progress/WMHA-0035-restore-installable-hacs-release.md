---
id: WMHA-0035
title: Restore an installable HACS release
status: in-progress
type: bug
priority: high
risk: medium
created: 2026-08-03
updated: 2026-08-03
depends_on: []
---

# WMHA-0035: Restore an installable HACS release

## Outcome

A user can download the integration through HACS as a custom repository without a download
error, and the release automation that produces the required asset runs on the repository's
actual default branch.

## Why

Reported from a live Home Assistant instance on 2026-08-03:

```
Download failed - Got status code 404 when trying to download
https://github.com/dprinz/ha-windmill-dev/releases/download/27a0f18/windmill.zip
```

Two independent defects produce and sustain this failure.

**1. No published release exists.** The GitHub API lists two releases for tag `v0.1.0`
(`untagged-f736b2b54dbdd89c0c58` and `untagged-2c4e0f3c966e7b79a947`), both with
`draft: true`. HACS does not see drafts. `docs/research/hacs-and-release-requirements.md`
(R-004) already records the consequence: without a release, HACS uses the first seven
characters of the last commit on the default branch as the remote version. That is
`27a0f18`, the current `master` HEAD, and it appears verbatim in the user's error. Because
`hacs.json` sets `zip_release: true` with `filename: windmill.zip`, HACS then requests
`releases/download/27a0f18/windmill.zip` — an asset that cannot exist, because `27a0f18` is
a commit, not a release tag. The 404 is the correct response to a URL that the missing
release forced HACS to construct.

**2. Every workflow targets a branch that no longer exists.** The repository's default
branch is `master` (`27a0f185c3aa730f8ae911af54bb90d6bdb94334`); the only other branch is
`agent/agentic-development-foundation`. There is no `main`. All four workflows still name
it:

- `release.yml:24` runs `git fetch --no-tags --depth=50 origin main`, which now fails with
  `couldn't find remote ref main`. This is the blocking defect: the next release tag cannot
  produce an asset at all. Release run 30772777447 (2026-08-02) still passed this step —
  its log shows `* [new branch] main -> origin/main` — so the branch existed then and was
  renamed afterwards.
- `checks.yml:7`, `repository-guardrails.yml:7` and `validate-hacs.yml:7` restrict their
  push trigger to `main`, so no push to the default branch has triggered CI since the
  rename. Pull-request triggers are unaffected.

## Required context

- `AGENTS.md`
- `docs/research/hacs-and-release-requirements.md` (R-004, R-006)
- `.github/workflows/release.yml`, `checks.yml`, `repository-guardrails.yml`,
  `validate-hacs.yml`
- `hacs.json`, `custom_components/windmill/manifest.json`
- `scripts/build_release.py`

## Requirements

- The release workflow must verify the tag against the repository's *actual* default
  branch, and must not break again if the default branch is renamed.
- Push-triggered workflows must run on the default branch.
- Do not weaken the existing branch verification: a tag that does not point at a commit on
  the default branch must still be refused.
- Do not change the draft-release design. Publishing stays a human decision
  (`AGENTS.md`, "Scope and safety"), so this ticket cannot close the user-visible 404 by
  itself; it removes the automation defect that blocks the fix and hands the publishing
  step over.
- Do not silently retag or publish. The release route was decided by the requester
  (see "Handover").

## Acceptance criteria

- [x] No workflow references a branch named `main`. Verified by
      `grep -rn "main" .github/workflows/`, which afterwards matches only the HACS action's
      unrelated `ghcr.io/hacs/action:main` image comment.
- [x] `release.yml` resolves the default branch from the GitHub event payload rather than a
      literal, so a future rename cannot reintroduce the failure. The branch name is passed
      through an environment variable, matching the file's existing convention for
      untrusted-shaped values.
- [x] `release.yml` still refuses a tag that is not an ancestor of the default branch; the
      `git merge-base --is-ancestor` guard and the non-zero exit are unchanged.
- [x] The three push-triggered workflows list `master`.
- [x] All four workflow files still parse as YAML and keep their previous `permissions`
      blocks.
- [ ] A published (non-draft) GitHub release exists whose tag matches
      `custom_components/windmill/manifest.json` and which carries a `windmill.zip` asset
      built by `scripts/build_release.py`. **Human step — see "Handover".** This criterion
      stays open until the requester publishes.

## Non-goals

- Publishing or deleting any release or tag from an agent session. `AGENTS.md` reserves
  that for explicit human action, and the available GitHub tooling in this session has no
  release-write capability.
- Changing `hacs.json`, the ZIP layout or `scripts/build_release.py`. R-006 verified the
  archive layout and the release run confirmed it builds
  (`sha256:f2514257f89ffb394d3eeeef2e57d9f48d3e0834cffd93a7c2ed599af0549022`).
- Bumping the version. `0.1.0` was never published, so it is still unreleased.
- Submitting to the HACS default store.

## Constraints

- Keep `permissions: contents: read` at workflow level and `contents: write` scoped to the
  release job only.
- Keep every action pinned by SHA or major tag exactly as it is; this is not a dependency
  ticket.
- The default-branch name must not be interpolated directly into a shell command.

## Assumptions and research needs

| Item | Classification | Validation |
| --- | --- | --- |
| `github.event.repository.default_branch` is populated for `push` events on tags | fact | GitHub Actions webhook payload documentation: `push` carries the full `repository` object, including `default_branch`. Confirmed by the next release run |
| The rename from `main` to `master` was intentional and `master` stays the default | assumption | Requester confirmed the release route on `master` HEAD on 2026-08-03 |
| HACS only considers non-draft releases | fact | `docs/research/hacs-and-release-requirements.md` R-004, and the observed 404 against the commit-sha URL |

## Validation evidence

| Check | Command or inspection | Result |
| --- | --- | --- |
| Repository guardrails | `python scripts/validate_repository.py` | 2026-08-03: passed (35 tickets checked) |
| No `main` branch reference left | `grep -rn "main" .github/workflows/` | 2026-08-03: only `validate-hacs.yml` comments about the `ghcr.io/hacs/action:main` image remain |
| Workflows still parse and keep permissions | `yaml.safe_load` of all four workflow files, compared against `git show HEAD:<file>` | 2026-08-03: parsed; `checks/guardrails/release` keep `{contents: read}`, `validate-hacs` keeps `{}`, the release job keeps `{contents: write}`; all identical to `HEAD` |
| Test, lint and type checks | `pytest`, `ruff`, `mypy` | not run — the change touches no Python or integration code, only workflow YAML. CI runs them on the branch |
| Branch guard intact | inspection of `release.yml` | 2026-08-03: `git merge-base --is-ancestor HEAD FETCH_HEAD` and `exit 1` unchanged; only the fetched ref is now resolved from the event payload |
| Default branch and releases on GitHub | GitHub API: `list_branches`, `list_releases`, `list_tags` | 2026-08-03: branches `master`, `agent/agentic-development-foundation`; releases both `draft: true`; tag `v0.1.0` at `d46902f` |
| Published release installs through HACS | requester's Home Assistant instance | not run — blocked on the human publishing step |

## Review evidence

- Reviewer/session: not yet reviewed. Risk is medium because the change touches release
  automation, so `AGENTS.md` asks for an independent review before this ticket moves to
  done.
- Findings: pending review.
- Resolution: pending review.

## Handover

The workflow fix does not make the integration installable on its own — only a published
release does. The requester chose to re-cut `v0.1.0` on `master` HEAD rather than publish
the existing draft, because tag `v0.1.0` points at `d46902f` and `master` has since gained
a code fix (`4dbc87e`, `custom_components/windmill/event.py`) that the draft's archive does
not contain. `0.1.0` was never published, so the tag is free to move and `CHANGELOG.md`
stays accurate.

Steps, all requiring repository write access:

1. Delete both draft releases in the GitHub UI (Releases → each draft → Delete).
2. Delete the tag: `git push origin :refs/tags/v0.1.0` and `git tag -d v0.1.0`.
3. Re-tag the merged default branch: `git checkout master && git pull` — this must include
   the workflow fix from this ticket — then `git tag -a v0.1.0 -m "Windmill v0.1.0"` and
   `git push origin v0.1.0`.
4. Wait for the `Release` workflow to finish and produce a new draft with `windmill.zip`.
5. Review the notes and **publish** the release (uncheck "Set as a pre-release" as
   appropriate, then "Publish release").
6. In Home Assistant, retry the HACS download and record the result in this ticket's
   validation evidence before moving it to `tickets/done/`.

## Residual risks and follow-up

- Nothing enforces that a release is published rather than left as a draft. A stale draft
  reproduces exactly this 404 for every user. A follow-up ticket could add a scheduled or
  post-release check that the latest release is non-draft and carries the expected asset.
- The HACS validator runs from a floating container image (R-005), so a passing validation
  is only reproducible per run date.
- Observed while validating, out of scope here: `uv run` refuses to start in a fresh
  environment because `.python-version` resolves to CPython `3.14.0rc2` while
  `pyproject.toml` requires `>=3.14.2` (`error: The Python request from .python-version
  resolved to Python 3.14.0rc2, which is incompatible with the project's Python
  requirement`). Every `uv run` command in `AGENTS.md` is unusable until the pin resolves to
  a final 3.14.2+ interpreter. This needs its own ticket; it did not block this change,
  which required no project interpreter.

## Blog notes

- A 404 for `releases/download/<commit-sha>/<asset>.zip` is not a broken URL; it is HACS
  reporting that no release exists. With `zip_release`, HACS falls back to the default
  branch's short commit SHA as the version and then asks for an asset under that
  non-existent tag. The draft state of a release is invisible to clients, which makes
  "built successfully" and "installable" two different things.
