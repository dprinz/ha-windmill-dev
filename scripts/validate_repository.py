#!/usr/bin/env python3
"""Validate the repository-native agent and ticket foundation."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_FILES = {
    "AGENTS.md",
    "docs/context-map.md",
    "docs/product/vision.md",
    "docs/architecture/overview.md",
    "docs/development/agent-workflow.md",
    "docs/development/security-and-trust.md",
    "docs/research/source-register.md",
    "tickets/README.md",
    "tickets/_templates/ticket.md",
    "plans/README.md",
    ".github/copilot-instructions.md",
}

STATE_DIRS = {
    "backlog": ROOT / "tickets" / "backlog",
    "ready": ROOT / "tickets" / "ready",
    "in-progress": ROOT / "tickets" / "in-progress",
    "done": ROOT / "tickets" / "done",
}

REQUIRED_TICKET_SECTIONS = (
    "## Outcome",
    "## Acceptance criteria",
    "## Non-goals",
    "## Validation evidence",
    "## Review evidence",
)

FRONTMATTER_RE = re.compile(r"\A---\n(?P<body>.*?)\n---\n", re.DOTALL)
FIELD_RE = re.compile(r"^(?P<key>[a-z_]+):\s*(?P<value>.*)$", re.MULTILINE)
LINK_RE = re.compile(r"(?<!!)\[[^]]+\]\((?P<target>[^)]+)\)")
TICKET_NAME_RE = re.compile(r"^WMHA-\d{4}-.+\.md$")


def parse_frontmatter(text: str, path: Path) -> dict[str, str]:
    match = FRONTMATTER_RE.match(text)
    if not match:
        raise ValueError(f"{path.relative_to(ROOT)}: missing YAML frontmatter")
    return {m.group("key"): m.group("value").strip() for m in FIELD_RE.finditer(match.group("body"))}


def validate_required_files(errors: list[str]) -> None:
    for relative in sorted(REQUIRED_FILES):
        if not (ROOT / relative).is_file():
            errors.append(f"missing required file: {relative}")


def validate_tickets(errors: list[str]) -> None:
    seen_ids: dict[str, Path] = {}
    for expected_status, directory in STATE_DIRS.items():
        if not directory.is_dir():
            errors.append(f"missing ticket state directory: {directory.relative_to(ROOT)}")
            continue
        for path in sorted(directory.glob("*.md")):
            if path.name == "README.md":
                continue
            if not TICKET_NAME_RE.match(path.name):
                errors.append(f"{path.relative_to(ROOT)}: ticket filename must match WMHA-NNNN-description.md")
            text = path.read_text(encoding="utf-8")
            try:
                metadata = parse_frontmatter(text, path)
            except ValueError as exc:
                errors.append(str(exc))
                continue
            ticket_id = metadata.get("id")
            status = metadata.get("status")
            if not ticket_id or not re.fullmatch(r"WMHA-\d{4}", ticket_id):
                errors.append(f"{path.relative_to(ROOT)}: invalid or missing id")
            elif ticket_id in seen_ids:
                errors.append(
                    f"duplicate ticket id {ticket_id}: {seen_ids[ticket_id].relative_to(ROOT)} and {path.relative_to(ROOT)}"
                )
            else:
                seen_ids[ticket_id] = path
            if status != expected_status:
                errors.append(
                    f"{path.relative_to(ROOT)}: status {status!r} does not match directory {expected_status!r}"
                )
            for section in REQUIRED_TICKET_SECTIONS:
                if section not in text:
                    errors.append(f"{path.relative_to(ROOT)}: missing section {section}")


def validate_local_links(errors: list[str]) -> None:
    for path in ROOT.rglob("*.md"):
        text = path.read_text(encoding="utf-8")
        for match in LINK_RE.finditer(text):
            target = match.group("target").strip()
            if not target or target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            clean_target = target.split("#", 1)[0]
            if not clean_target:
                continue
            resolved = (path.parent / clean_target).resolve()
            try:
                resolved.relative_to(ROOT.resolve())
            except ValueError:
                errors.append(f"{path.relative_to(ROOT)}: link escapes repository: {target}")
                continue
            if not resolved.exists():
                errors.append(f"{path.relative_to(ROOT)}: broken local link: {target}")


def main() -> int:
    errors: list[str] = []
    validate_required_files(errors)
    validate_tickets(errors)
    validate_local_links(errors)

    if errors:
        print("Repository validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    ticket_count = sum(
        1
        for directory in STATE_DIRS.values()
        for path in directory.glob("*.md")
        if path.name != "README.md"
    )
    print(f"Repository validation passed ({ticket_count} tickets checked).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
