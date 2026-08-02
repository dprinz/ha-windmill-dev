# HACS packaging and GitHub release requirements

Research for WMHA-0014. All facts verified on 2026-08-02 against the primary sources listed.
Retrieved content was treated as untrusted data; no instructions were taken from it.

## R-001: hacs.json schema and location

- Claim: `hacs.json` must sit in the repository root. Required key: `name`. Optional keys
  include `content_in_root`, `zip_release` (integrations only; requires `filename`),
  `filename`, `hide_default_branch`, `country`, `homeassistant` (minimum HA version),
  `hacs` (minimum HACS version) and `persistent_directory`.
- Source: https://www.hacs.xyz/docs/publish/start/ (HACS documentation, "General requirements")
- Verification date: 2026-08-02
- Confidence: high
- Implication: this repository needs a root `hacs.json` with at least `name`; for a
  release-attached ZIP it needs `zip_release: true` and `filename: windmill.zip`.

## R-002: Integration repository structure

- Claim: one integration per repository, located at
  `ROOT/custom_components/<domain>/`; all runtime files inside that directory.
  The integration `manifest.json` must define at least `domain`, `documentation`,
  `issue_tracker`, `codeowners`, `name` and `version`.
- Source: https://www.hacs.xyz/docs/publish/integration/ (HACS documentation)
- Verification date: 2026-08-02
- Confidence: high
- Implication: the repository layout already complies, but `manifest.json` (version 0.1.0)
  lacks `issue_tracker` and must gain it.

## R-003: Brand assets

- Claim: an integration repository must provide brand assets — a `brand/` directory with at
  least `icon.png`. For default-store inclusion HACS falls back to the
  `home-assistant/brands` repository; the `brands` check can be ignored in the HACS action,
  but a default submission must pass "without any errors or ignores".
- Sources: https://www.hacs.xyz/docs/publish/integration/ and
  https://www.hacs.xyz/docs/publish/include/ and
  https://www.hacs.xyz/docs/publish/action/ (list of ignorable checks)
- Verification date: 2026-08-02
- Confidence: high
- Implication: add `brand/icon.png` so CI validation passes without ignores; a submission to
  `home-assistant/brands` remains follow-up work outside this ticket.

## R-004: Version source for HACS

- Claim: if the repository publishes GitHub releases, HACS uses the tag name of the latest
  release as the remote version. Tags alone are not enough — a full release is required.
  Without releases, HACS uses the first 7 characters of the last commit of the default
  branch.
- Source: https://www.hacs.xyz/docs/publish/start/ ("Versions")
- Verification date: 2026-08-02
- Confidence: high
- Implication: the release workflow must create a GitHub release (draft until human
  approval), not only push a tag. The tag, the manifest `version` and the artifact must
  agree, because HACS compares the release tag with the installed manifest version.

## R-005: HACS validation action

- Claim: the official action is `hacs/action` with `category: integration`; the documented
  workflow uses `permissions: {}`. Ignorable checks include `archived`, `brands`,
  `description`, `hacsjson`, `images`, `information`, `issues`, `topics`.
- Source: https://www.hacs.xyz/docs/publish/action/
- Verification date: 2026-08-02
- Confidence: high
- Pinning fact: the action is a Docker action. Both `main` and the latest release tag
  (`22.5.0`, the newest tag per the GitHub API on 2026-08-02) declare
  `image: "docker://ghcr.io/hacs/action:main"` in their `action.yml`, so the validator code
  always comes from the floating `main` container image regardless of the pinned git ref.
  Verified by fetching `action.yml` at both refs on 2026-08-02. `main` HEAD was
  `1ebf01c408f29afcb6406bd431bc98fd8cbb15aa` (2026-06-08).
- Implication: pin the git ref by SHA to control the action definition, but document that
  the validator itself is not reproducibly pinned; a HACS-side change can alter results.

## R-006: ZIP release extraction behavior

- Claim: for `zip_release` integrations, HACS downloads the release asset named by
  `filename` and extracts it **directly into** `<config>/custom_components/<domain>/`
  (`zip_file.extractall(self.content.path.local)`). The ZIP must therefore contain the
  integration files (`manifest.json`, `__init__.py`, …) at its root, without a wrapping
  directory. Wrapping the files in a `windmill/` folder produces a double-nested
  `custom_components/windmill/windmill/` install that fails to load.
- Sources: HACS source `custom_components/hacs/repositories/base.py`,
  `async_download_zip_file` (main branch, fetched 2026-08-02); the double-nesting failure is
  independently reported in https://github.com/jrhubott/adaptive-cover-pro/issues/544.
- Verification date: 2026-08-02
- Confidence: high
- Implication: the release workflow builds `windmill.zip` from the *contents* of
  `custom_components/windmill/`, not from the directory itself.

## R-007: Default-store inclusion vs. custom repository

- Claim: inclusion in the HACS default store requires a manual pull request to
  `hacs/default`, passing HACS action and hassfest without ignores, and at least one GitHub
  release. Review takes months. Installation as a HACS *custom repository* works without
  any of that as long as the repository meets the general and integration requirements.
- Source: https://www.hacs.xyz/docs/publish/include/
- Verification date: 2026-08-02
- Confidence: high
- Implication: the README documents the custom-repository path; a default-store submission
  is deliberate follow-up work, not part of WMHA-0014.

## R-008: hassfest for custom integrations

- Claim: hassfest (Home Assistant's own manifest/structure validator) is the standard
  companion check for custom integrations and is required for default-store inclusion.
  The action `home-assistant/actions/hassfest` is only maintained on the `master` branch;
  the single tag (`1.0.0`) is stale. Upstream documents `uses:
  home-assistant/actions/hassfest@master`. `master` HEAD was
  `ab22029681aa532bfe7de5774a9972d67bfbd2c0` (2026-07-30) on the verification date.
- Sources: https://github.com/home-assistant/actions (tags and branches via GitHub API);
  recommended by https://www.hacs.xyz/docs/publish/action/ ("you can also validate your
  integration with hassfest")
- Verification date: 2026-08-02
- Confidence: high
- Implication: pin hassfest to the verified `master` SHA with a comment; the ref must be
  re-checked when CI behavior changes.

## Unresolved ambiguity

- The HACS action's floating `main` Docker image (R-005) means "HACS validation passes" is
  only reproducible per CI run date, not per commit. Mitigation: record the run date in
  release evidence and re-run validation on tags.
- `homeassistant` minimum version in `hacs.json`: set to `2026.7.0` because the test
  baseline is Home Assistant 2026.7.4 (see `docs/development/testing-strategy.md`). Older
  versions are untested.
