#!/usr/bin/env python3
"""Validate that a pull request body fills the review quality gate template."""

from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass


REQUIRED_SECTIONS = (
    "Summary",
    "Contract Impact",
    "RBAC / Permissions",
    "Notification / Realtime",
    "Frontend Resilience",
    "Scope Gate",
    "Validation",
)

REQUIRED_FIELDS_BY_SECTION = {
    "Contract Impact": (
        "Canonical surface",
        "Request shape",
        "Response shape",
        "Status codes",
        "Frontend consumer",
        "Compatibility path or alias",
        "Contract proof",
    ),
    "RBAC / Permissions": (
        "Roles allowed",
        "Roles denied",
        "Positive auth proof",
        "Negative auth proof",
    ),
    "Notification / Realtime": (
        "Event type or websocket channel",
        "Payload version / ack behavior",
        "Read/unread or delivery semantics",
        "Reconnect/resync proof",
    ),
    "Frontend Resilience": (
        "Empty data proof",
        "Partial data proof",
        "Forbidden secondary path behavior",
        "Missing draft/resource behavior",
        "Stale route/deep-link behavior",
    ),
    "Scope Gate": (
        "Allowed paths",
        "Denied paths",
        "Migration/docs/test impact",
        "Rollback note",
    ),
    "Validation": (
        "Targeted tests or smoke run",
        "Result",
        "Not checked",
    ),
}

PLACEHOLDER_PATTERNS = (
    r"describe the change in 2-4 bullets",
    r"canonical surface:\s*$",
    r"request shape:\s*$",
    r"response shape:\s*$",
    r"status codes:\s*$",
    r"frontend consumer:\s*$",
    r"compatibility path or alias:\s*$",
    r"contract proof:\s*$",
    r"roles allowed:\s*$",
    r"roles denied:\s*$",
    r"positive auth proof:\s*$",
    r"negative auth proof:\s*$",
    r"targeted tests or smoke run:\s*$",
    r"result:\s*$",
)

FIELD_RE = re.compile(r"^[ \t]*-[ \t]*([^:\n]+):[ \t]*(.*?)[ \t]*$", re.MULTILINE)
HEADING_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
UTF8_BOM = "\ufeff"


@dataclass(frozen=True)
class ValidationResult:
    errors: list[str]
    warnings: list[str]


def _read_body(args: argparse.Namespace) -> str:
    if args.body_env:
        return os.environ.get(args.body_env, "")
    if args.body_file:
        with open(args.body_file, "r", encoding="utf-8") as handle:
            return handle.read()
    return sys.stdin.read()


def _extract_sections(body: str) -> dict[str, str]:
    matches = list(HEADING_RE.finditer(body))
    sections: dict[str, str] = {}
    for index, match in enumerate(matches):
        title = match.group(1).strip()
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        sections[title] = body[start:end].strip()
    return sections


def _strip_html_comments(text: str) -> str:
    return HTML_COMMENT_RE.sub("", text)


def _strip_utf8_bom(text: str) -> str:
    return text.lstrip(UTF8_BOM)


def _strip_guidance_lines(text: str) -> str:
    text = _strip_html_comments(text)
    kept: list[str] = []
    for line in text.splitlines():
        normalized = line.strip().lower()
        if normalized.startswith("if no "):
            continue
        if normalized.startswith("see `docs/runbooks/pr_review_quality_gates.md`"):
            continue
        kept.append(line)
    return "\n".join(kept).strip()


def _has_meaningful_text(text: str) -> bool:
    cleaned = _strip_guidance_lines(text)
    if not cleaned:
        return False

    lowered = cleaned.lower()
    if "not applicable" in lowered:
        return True

    placeholder_hits = 0
    for pattern in PLACEHOLDER_PATTERNS:
        if re.search(pattern, lowered, flags=re.MULTILINE):
            placeholder_hits += 1

    field_values = [value.strip() for _, value in FIELD_RE.findall(cleaned)]
    non_empty_values = [value for value in field_values if value and value.lower() != "n/a"]

    if field_values:
        return bool(non_empty_values)

    return placeholder_hits == 0 and len(cleaned.split()) >= 4


def _has_not_applicable_reason(text: str) -> bool:
    cleaned = _strip_guidance_lines(text).strip()
    match = re.search(r"\bnot applicable\b\s*(?:[-:;,]|\sbecause\b)\s*(.+)", cleaned, re.I)
    if not match:
        return False
    reason = match.group(1).strip()
    return len(reason.split()) >= 3


def _missing_required_field_answers(section: str, text: str) -> list[str]:
    required_fields = REQUIRED_FIELDS_BY_SECTION.get(section, ())
    if not required_fields:
        return []

    cleaned = _strip_guidance_lines(text)
    field_pairs = FIELD_RE.findall(cleaned)
    if not field_pairs and _has_not_applicable_reason(cleaned):
        return []

    fields = {name.strip().lower(): value.strip() for name, value in field_pairs}
    missing: list[str] = []

    for field in required_fields:
        value = fields.get(field.lower(), "")
        if not value or value.lower() == "n/a":
            missing.append(field)
            continue
        if value.lower() == "not applicable" or (
            value.lower().startswith("not applicable") and not _has_not_applicable_reason(value)
        ):
            missing.append(field)

    return missing


def validate_pr_body(body: str) -> ValidationResult:
    errors: list[str] = []
    warnings: list[str] = []
    body = _strip_utf8_bom(body)
    body = _strip_html_comments(body)

    if not body.strip():
        return ValidationResult(
            errors=["PR body is empty. Fill the review quality gate template."],
            warnings=[],
        )

    sections = _extract_sections(body)
    for required in REQUIRED_SECTIONS:
        if required not in sections:
            errors.append(f"Missing required section: ## {required}")
            continue
        if not _has_meaningful_text(sections[required]):
            errors.append(
                f"Section ## {required} still looks empty. Fill it or write "
                "`not applicable` with a short reason."
            )
            continue
        missing_fields = _missing_required_field_answers(required, sections[required])
        if missing_fields:
            errors.append(
                f"Section ## {required} has unanswered required fields: "
                + ", ".join(missing_fields)
            )

    if "not applicable" in body.lower():
        warnings.append(
            "`not applicable` is accepted, but reviewers should confirm the reason is specific."
        )

    return ValidationResult(errors=errors, warnings=warnings)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate PR review quality gate template completion."
    )
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--body-file", help="Path to a markdown file containing PR body.")
    source.add_argument("--body-env", help="Environment variable containing PR body text.")
    args = parser.parse_args()

    body = _read_body(args)
    result = validate_pr_body(body)

    for warning in result.warnings:
        print(f"warning: {warning}")

    if result.errors:
        print("PR review quality gate failed:")
        for error in result.errors:
            print(f"- {error}")
        return 1

    print("PR review quality gate passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
