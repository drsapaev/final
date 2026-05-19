"""Generate release-note bullets from newly checked Telegram roadmap items."""

from __future__ import annotations

import argparse
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path


DEFAULT_PLAN_PATH = ".ai-factory/plans/telegram-bot-clinic-full-strategy.md"
HEADING_RE = re.compile(r"^(?P<marks>#{1,6})\s+(?P<title>.+?)\s*$")
CHECKED_RE = re.compile(r"^\s*-\s+\[x\]\s+(?P<text>.+?)\s*$", re.I)
EXCLUDED_SECTIONS = {"Implementation Status Legend"}


@dataclass(frozen=True)
class CheckedItem:
    section: str
    text: str


def _section_path(stack: list[tuple[int, str]]) -> str:
    if not stack:
        return "(no section)"
    return " > ".join(title for _level, title in stack)


def checked_items_from_text(plan_text: str) -> list[CheckedItem]:
    section_stack: list[tuple[int, str]] = []
    checked: list[CheckedItem] = []

    for raw_line in plan_text.splitlines():
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

        item = CHECKED_RE.match(raw_line)
        if not item:
            continue
        if any(title in EXCLUDED_SECTIONS for _level, title in section_stack):
            continue
        checked.append(
            CheckedItem(section=_section_path(section_stack), text=item.group("text").strip())
        )
    return checked


def _git_show_text(ref: str, path: str) -> str:
    result = subprocess.run(
        ["git", "show", f"{ref}:{path}"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def newly_checked_items(base_text: str, head_text: str) -> list[CheckedItem]:
    base_checked = {item.text for item in checked_items_from_text(base_text)}
    return [
        item
        for item in checked_items_from_text(head_text)
        if item.text not in base_checked
    ]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate Telegram release-note bullets from newly checked plan items."
    )
    parser.add_argument("--base", default="origin/main", help="Base git ref.")
    parser.add_argument("--head", default="HEAD", help="Head git ref.")
    parser.add_argument(
        "--plan-path",
        default=DEFAULT_PLAN_PATH,
        help=f"Plan path inside git refs. Defaults to {DEFAULT_PLAN_PATH}.",
    )
    parser.add_argument(
        "--base-plan",
        type=Path,
        help="Read base plan from a file instead of git.",
    )
    parser.add_argument(
        "--head-plan",
        type=Path,
        help="Read head plan from a file instead of git.",
    )
    args = parser.parse_args()

    if bool(args.base_plan) != bool(args.head_plan):
        parser.error("--base-plan and --head-plan must be provided together")

    if args.base_plan and args.head_plan:
        base_text = _read_text(args.base_plan)
        head_text = _read_text(args.head_plan)
        source = f"{args.base_plan}..{args.head_plan}"
    else:
        base_text = _git_show_text(args.base, args.plan_path)
        head_text = _git_show_text(args.head, args.plan_path)
        source = f"{args.base}:{args.plan_path}..{args.head}:{args.plan_path}"

    items = newly_checked_items(base_text, head_text)
    print("# Telegram Plan Release Notes")
    print(f"Source: {source}")
    print(f"Newly checked items: {len(items)}")
    for item in items:
        print(f"- {item.section}: {item.text}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
