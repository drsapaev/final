"""Print unchecked Telegram roadmap items for release review.

The script intentionally uses only the standard library so it can run in CI,
from a developer shell, or inside an agent handoff without project setup.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path


DEFAULT_PLAN_PATH = Path(".ai-factory/plans/telegram-bot-clinic-full-strategy.md")
HEADING_RE = re.compile(r"^(?P<marks>#{1,6})\s+(?P<title>.+?)\s*$")
UNCHECKED_RE = re.compile(r"^(?P<indent>\s*)-\s+\[\s\]\s+(?P<text>.+?)\s*$")
EXCLUDED_SECTIONS = {"Implementation Status Legend"}


def _section_path(stack: list[tuple[int, str]]) -> str:
    if not stack:
        return "(no section)"
    return " > ".join(title for _level, title in stack)


def iter_unchecked_items(plan_path: Path) -> list[tuple[int, str, str]]:
    """Return unchecked checkbox items as (line_number, section, text)."""
    section_stack: list[tuple[int, str]] = []
    unchecked: list[tuple[int, str, str]] = []

    for line_number, raw_line in enumerate(plan_path.read_text(encoding="utf-8").splitlines(), 1):
        heading = HEADING_RE.match(raw_line)
        if heading:
            level = len(heading.group("marks"))
            title = heading.group("title").strip()
            section_stack = [
                (existing_level, existing_title)
                for existing_level, existing_title in section_stack
                if existing_level < level
            ]
            section_stack.append((level, title))
            continue

        item = UNCHECKED_RE.match(raw_line)
        if item:
            section = _section_path(section_stack)
            if any(title in EXCLUDED_SECTIONS for _level, title in section_stack):
                continue
            unchecked.append((line_number, section, item.group("text").strip()))

    return unchecked


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Print unchecked Telegram strategy plan items for release review."
    )
    parser.add_argument(
        "--plan",
        type=Path,
        default=DEFAULT_PLAN_PATH,
        help=f"Plan path to inspect. Defaults to {DEFAULT_PLAN_PATH}.",
    )
    args = parser.parse_args()

    plan_path = args.plan
    if not plan_path.exists():
        parser.error(f"plan file not found: {plan_path}")

    unchecked = iter_unchecked_items(plan_path)
    print(f"Unchecked Telegram roadmap items: {len(unchecked)}")
    print(f"Plan: {plan_path}")

    for line_number, section, text in unchecked:
        print(f"{line_number}: {section} :: {text}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
