#!/usr/bin/env python3
"""Format or append a PR review adoption log entry."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LOG_PATH = REPO_ROOT / "docs" / "runbooks" / "PR_REVIEW_ADOPTION_LOG.md"
LOG_HEADING = "## Log"
VALID_RESULTS = ("passed", "failed", "partial", "not run")


@dataclass(frozen=True)
class AdoptionEntry:
    entry_date: str
    focus: str
    track: str
    evidence: str
    gate_result: str
    repeated_gap: str
    prevention: str
    next_action: str


def format_entry(entry: AdoptionEntry) -> str:
    return "\n".join(
        [
            f"## {entry.entry_date} - {entry.focus}",
            "",
            f"- Track: {entry.track}",
            f"- Evidence reviewed: {entry.evidence}",
            f"- Gate result: {entry.gate_result}",
            f"- Repeated gap observed: {entry.repeated_gap}",
            f"- Prevention added: {entry.prevention}",
            f"- Next action: {entry.next_action}",
            "",
        ]
    )


def append_entry(log_text: str, entry_text: str) -> str:
    if LOG_HEADING not in log_text:
        raise ValueError(f"Could not find `{LOG_HEADING}` heading in adoption log.")

    marker = f"{LOG_HEADING}\n"
    before, after = log_text.split(marker, 1)
    existing_log = after.lstrip("\n")
    return f"{before}{marker}\n{entry_text}{existing_log}"


def _required_text(value: str, field_name: str) -> str:
    value = value.strip()
    if not value:
        raise SystemExit(f"{field_name} cannot be empty.")
    return value


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Create a PR review adoption log entry. By default prints the entry; "
            "use --write to append it to the log."
        )
    )
    parser.add_argument("--date", default=date.today().isoformat(), help="Entry date.")
    parser.add_argument("--focus", required=True, help="PR, branch, or focus label.")
    parser.add_argument("--track", required=True, help="Skill track name.")
    parser.add_argument("--evidence", required=True, help="Evidence reviewed.")
    parser.add_argument(
        "--gate-result",
        required=True,
        choices=VALID_RESULTS,
        help="Gate result.",
    )
    parser.add_argument("--gap", required=True, help="Repeated gap observed, or none.")
    parser.add_argument("--prevention", required=True, help="Prevention added, or none.")
    parser.add_argument("--next-action", required=True, help="Smallest next action.")
    parser.add_argument(
        "--log-file",
        default=str(DEFAULT_LOG_PATH),
        help="Adoption log file to update when --write is set.",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Append the entry to the adoption log instead of only printing it.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    entry = AdoptionEntry(
        entry_date=_required_text(args.date, "--date"),
        focus=_required_text(args.focus, "--focus"),
        track=_required_text(args.track, "--track"),
        evidence=_required_text(args.evidence, "--evidence"),
        gate_result=_required_text(args.gate_result, "--gate-result"),
        repeated_gap=_required_text(args.gap, "--gap"),
        prevention=_required_text(args.prevention, "--prevention"),
        next_action=_required_text(args.next_action, "--next-action"),
    )
    entry_text = format_entry(entry)

    if not args.write:
        print(entry_text, end="")
        return 0

    log_path = Path(args.log_file)
    log_text = log_path.read_text(encoding="utf-8")
    log_path.write_text(append_entry(log_text, entry_text), encoding="utf-8")
    print(f"Appended adoption entry to {log_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
