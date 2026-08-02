---
id: WMHA-0025
title: Fix HACS validation failures for license and brands
status: done
type: quality
priority: high
risk: low
created: 2026-08-02
updated: 2026-08-02
depends_on: [WMHA-0014]
---

# WMHA-0025: Fix HACS validation failures for license and brands

## Outcome

The HACS validation workflow passes on `main`.

## Context

Found on the first CI run of `validate-hacs.yml` (run 30758262806, 2026-08-02). Two of nine
checks failed:

- `license`: the repository has no license file.
- `brands`: the action looks for brand assets at `custom_components/windmill/brand/icon.png`,
  not at the repository root, and the domain is not listed in `home-assistant/brands`.

This contradicts research note R-003 in `docs/research/hacs-and-release-requirements.md`, which
claimed a root-level `brand/` directory satisfies the check. The note must be corrected with the
new verification date.

## Acceptance criteria

- [x] The repository carries an OSI-approved license file at the root.
- [x] Brand assets exist where the HACS action looks for them.
- [x] The `Validate HACS and hassfest` workflow concludes successfully on `main`.
- [x] Research note R-003 is corrected with source and verification date.

## Non-goals

- Submitting brand assets to `home-assistant/brands` (remains maintainer follow-up).
- Changing the release workflow or the integration code.

## Validation evidence

| Check | Command or inspection | Result |
| --- | --- | --- |
| Repository guardrails | `python scripts/validate_repository.py` | passed (25 tickets checked) |
| Test suite | `uv run pytest -q` | 385 passed |
| Archive still contains brand assets | `python scripts/build_release.py --tag v0.1.0` | passed (`brand/icon.png`, `brand/icon@2x.png` in `windmill.zip`) |
| HACS CI run | `gh run list` / `gh run view` (run 30758487986) | `Validate HACS and hassfest`: success on `main` (2026-08-02); guardrails run 30758488003 also success |

## Review evidence

- Reviewer/session: not needed (low risk, per AGENTS.md)
- Findings: none
- Resolution: n/a
