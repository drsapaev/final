"""Report test or smoke evidence for checked Telegram roadmap items.

The script is report-only by default. Use ``--fail-on-missing`` when the plan
is ready for strict evidence coverage.
"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path


DEFAULT_PLAN_PATH = Path(".ai-factory/plans/telegram-bot-clinic-full-strategy.md")
HEADING_RE = re.compile(r"^(?P<marks>#{1,6})\s+(?P<title>.+?)\s*$")
CHECKED_RE = re.compile(r"^(?P<indent>\s*)-\s+\[x\]\s+(?P<text>.+?)\s*$", re.I)
EXCLUDED_SECTIONS = {"Implementation Status Legend"}
EVIDENCE_RE = re.compile(
    r"(`[^`]*(?:test|tests|pytest|smoke|scripts/|backend/tests|frontend/src/.+__tests__)[^`]*`|"
    r"backend/tests/[^\s),;]+|frontend/src/[^\s),;]+__tests__/[^\s),;]+|"
    r"scripts/[^\s),;]+|pytest|smoke)",
    re.I,
)


@dataclass(frozen=True)
class CheckedRoadmapItem:
    line_number: int
    section: str
    text: str
    evidence: tuple[str, ...]


def _section_path(stack: list[tuple[int, str]]) -> str:
    if not stack:
        return "(no section)"
    return " > ".join(title for _level, title in stack)


def iter_checked_items(plan_path: Path) -> list[CheckedRoadmapItem]:
    section_stack: list[tuple[int, str]] = []
    checked: list[CheckedRoadmapItem] = []

    for line_number, raw_line in enumerate(
        plan_path.read_text(encoding="utf-8").splitlines(), 1
    ):
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

        text = item.group("text").strip()
        evidence = tuple(match.strip("`") for match in EVIDENCE_RE.findall(text))
        checked.append(
            CheckedRoadmapItem(
                line_number=line_number,
                section=_section_path(section_stack),
                text=text,
                evidence=evidence,
            )
        )
    return checked


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Report test or smoke evidence for checked Telegram roadmap items."
    )
    parser.add_argument(
        "--plan",
        type=Path,
        default=DEFAULT_PLAN_PATH,
        help=f"Plan path to inspect. Defaults to {DEFAULT_PLAN_PATH}.",
    )
    parser.add_argument(
        "--only-missing",
        action="store_true",
        help="Print only checked items without test/smoke evidence.",
    )
    parser.add_argument(
        "--fail-on-missing",
        action="store_true",
        help="Exit with status 1 when checked items lack test/smoke evidence.",
    )
    args = parser.parse_args()

    plan_path = args.plan
    if not plan_path.exists():
        parser.error(f"plan file not found: {plan_path}")

    checked_items = iter_checked_items(plan_path)
    missing = [item for item in checked_items if not item.evidence]
    print(f"Checked Telegram roadmap items: {len(checked_items)}")
    print(f"Checked items missing test/smoke evidence: {len(missing)}")
    print(f"Plan: {plan_path}")

    for item in checked_items:
        if args.only_missing and item.evidence:
            continue
        evidence = ", ".join(item.evidence) if item.evidence else "MISSING"
        print(f"{item.line_number}: {item.section} :: {evidence} :: {item.text}")

    return 1 if args.fail_on_missing and missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
