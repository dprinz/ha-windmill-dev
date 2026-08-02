# Versioning and releases

Conventions introduced with WMHA-0014. External facts behind them are sourced in
`docs/research/hacs-and-release-requirements.md`.

## Versioning convention

- Versions follow [Semantic Versioning](https://semver.org/): `MAJOR.MINOR.PATCH`.
- Breaking configuration, entity or behavior changes increment MAJOR; new
  backwards-compatible functionality increments MINOR; fixes increment PATCH.
  Before 1.0.0, MINOR may contain breaking changes (standard SemVer 0.x rule).
- Releases are tagged `v<version>` (for example `v0.2.0`).
- The tag version must equal `version` in
  `custom_components/windmill/manifest.json`. HACS compares the release tag with
  the installed manifest version, so a mismatch breaks update detection. The
  release workflow refuses to build when they disagree
  (`scripts/build_release.py`).

## Changelog convention

`CHANGELOG.md` follows the Keep a Changelog format. Every tagged release gets an
`## [x.y.z] - YYYY-MM-DD` section before the tag is pushed. Release notes on
GitHub mirror that entry inside the skeleton sections (Breaking Changes,
Permissions, Migration Notes, Changes) from
`scripts/release_notes_template.md`.

## Release runbook

Releasing is a deliberate human process; automation only builds and stages.

1. Ensure CI is green on `main` (tests, guardrails, HACS validation, hassfest).
2. Bump `version` in `custom_components/windmill/manifest.json`.
3. Add the `CHANGELOG.md` section for the new version.
4. Merge the version bump to `main` through the normal review process.
5. Create and push the tag locally: `git tag v<version> <commit-on-main>` and
   `git push origin v<version>`. The tag must point to a commit on `main`; the
   release workflow verifies this and stops otherwise. (The check fetches the
   last 50 commits of `main`; for an unusually old tag point, release from a
   recent commit instead.)
6. The `Release` workflow builds `windmill.zip` (files at the archive root, as
   HACS requires), verifies the tag/manifest match and creates a **draft**
   release with the notes skeleton and the archive attached.
7. A human fills in the release notes — Breaking Changes, Permissions and
   Migration Notes are mandatory sections, write `None.` where empty — and
   publishes the draft. Nothing is ever published automatically.

The ZIP archive is byte-reproducible for a given commit (fixed timestamps,
sorted entries); `scripts/build_release.py` prints its SHA-256 for comparison.

## One-time GitHub repository settings

The HACS validation action checks repository metadata that can only be set by a
maintainer on GitHub, not from a commit. Verified on 2026-08-02: the repository
had **no description and no topics**, which fails the `description` and `topics`
checks. Set them once (or via the web UI):

```bash
gh repo edit dprinz/ha-windmill-dev \
  --description "Home Assistant custom integration for Windmill.dev" \
  --add-topic home-assistant --add-topic hacs --add-topic windmill \
  --add-topic custom-integration
```

Issues are already enabled and the repository is public and not archived, so no
further settings are needed.

## Local checks

```bash
python scripts/build_release.py --tag v$(python3 -c "import json;print(json.load(open('custom_components/windmill/manifest.json'))['version'])") --output /tmp/release-test
```

This must succeed and print a SHA-256; a tag/manifest mismatch must exit
non-zero. The HACS and hassfest validations themselves only run in CI
(`hacs/action` and `home-assistant/actions/hassfest` have no supported local
mode without secrets).
