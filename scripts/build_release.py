#!/usr/bin/env python3
"""Build the HACS-compatible release archive for the Windmill integration.

Verifies that the release tag matches the integration manifest version, then
packages the contents of ``custom_components/windmill`` into ``windmill.zip``
with the files at the ZIP root. HACS extracts a ``zip_release`` asset directly
into ``custom_components/<domain>/`` (see
docs/research/hacs-and-release-requirements.md, R-006), so a wrapping directory
inside the ZIP would produce a broken double-nested installation.

Usage:
    python scripts/build_release.py --tag v0.1.0 --output dist
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
INTEGRATION_DIR = REPO_ROOT / "custom_components" / "windmill"
MANIFEST_PATH = INTEGRATION_DIR / "manifest.json"
ZIP_NAME = "windmill.zip"


class ReleaseError(Exception):
    """A release precondition failed."""


def read_manifest_version() -> str:
    """Return the version declared in the integration manifest."""
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    version = manifest.get("version")
    if not isinstance(version, str) or not version:
        raise ReleaseError(f"{MANIFEST_PATH} does not declare a non-empty 'version'")
    return version


def check_tag_matches_manifest(tag: str) -> str:
    """Return the version if the tag matches the manifest version, else raise."""
    if not tag.startswith("v"):
        raise ReleaseError(f"release tag {tag!r} must start with 'v' (expected format: v1.2.3)")
    version = tag.removeprefix("v")
    manifest_version = read_manifest_version()
    if version != manifest_version:
        raise ReleaseError(
            f"tag version {version!r} does not match manifest version "
            f"{manifest_version!r} in {MANIFEST_PATH}; bump the manifest or retag"
        )
    return version


def build_zip(output_dir: Path) -> Path:
    """Write the release ZIP with integration files at the archive root."""
    output_dir.mkdir(parents=True, exist_ok=True)
    zip_path = output_dir / ZIP_NAME
    files = sorted(
        path
        for path in INTEGRATION_DIR.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts
    )
    if not files:
        raise ReleaseError(f"no files found under {INTEGRATION_DIR}")
    # Fixed timestamp and explicit compression keep the archive reproducible.
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            info = zipfile.ZipInfo.from_file(path, arcname=path.relative_to(INTEGRATION_DIR))
            info.date_time = (1980, 1, 1, 0, 0, 0)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, path.read_bytes())
    return zip_path


def main(argv: list[str] | None = None) -> int:
    """Run the release build."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", required=True, help="release tag, for example v0.1.0")
    parser.add_argument(
        "--output",
        type=Path,
        default=REPO_ROOT / "dist",
        help="output directory for the release archive (default: dist/)",
    )
    args = parser.parse_args(argv)

    try:
        version = check_tag_matches_manifest(args.tag)
        zip_path = build_zip(args.output)
    except ReleaseError as err:
        print(f"error: {err}", file=sys.stderr)
        return 1

    digest = hashlib.sha256(zip_path.read_bytes()).hexdigest()
    print(f"version: {version}")
    print(f"archive: {zip_path}")
    print(f"sha256: {digest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
