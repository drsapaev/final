"""Check Telegram strategy plan content for stale rollout values.

Default behavior is warning-only. Use ``--fail-on-warning`` when wiring this
into CI or a release gate.
"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path


DEFAULT_PLAN_PATH = Path(".ai-factory/plans/telegram-bot-clinic-full-strategy.md")
SUPPORTED_LANGUAGE_CODES = {"ru", "uz-Latn"}
UNSUPPORTED_LANGUAGE_CODES = {"en", "en-US", "ru-RU", "uz", "uz-Cyrl"}
STALE_PROVIDER_NAMES = {"apelsin"}
STALE_PROVIDER_ALLOWED_CONTEXT = (
    "explicitly remove apelsin",
    "non-apelsin",
    "not apelsin",
    "not supported",
)
PLACEHOLDER_URL_RE = re.compile(
    r"https?://[^\s`)]*(?:clinic\.example\.com|example\.com|localhost|127\.0\.0\.1)",
    re.IGNORECASE,
)
CODE_SPAN_RE = re.compile(r"`([^`]+)`")


@dataclass(frozen=True)
class PlanContentWarning:
    line_number: int
    category: str
    detail: str
    text: str


def _stale_provider_allowed(line: str) -> bool:
    normalized = line.lower()
    return any(context in normalized for context in STALE_PROVIDER_ALLOWED_CONTEXT)


def iter_plan_content_warnings(plan_text: str) -> list[PlanContentWarning]:
    warnings: list[PlanContentWarning] = []
    for line_number, line in enumerate(plan_text.splitlines(), 1):
        normalized = line.lower()
        for provider in STALE_PROVIDER_NAMES:
            if provider in normalized and not _stale_provider_allowed(line):
                warnings.append(
                    PlanContentWarning(
                        line_number=line_number,
                        category="stale_provider",
                        detail=f"stale provider name: {provider}",
                        text=line.strip(),
                    )
                )

        for code in CODE_SPAN_RE.findall(line):
            if code in UNSUPPORTED_LANGUAGE_CODES:
                warnings.append(
                    PlanContentWarning(
                        line_number=line_number,
                        category="unsupported_language",
                        detail=(
                            f"unsupported language code: {code}; "
                            f"supported={sorted(SUPPORTED_LANGUAGE_CODES)}"
                        ),
                        text=line.strip(),
                    )
                )

        if PLACEHOLDER_URL_RE.search(line):
            warnings.append(
                PlanContentWarning(
                    line_number=line_number,
                    category="placeholder_url",
                    detail="hardcoded placeholder/local URL",
                    text=line.strip(),
                )
            )
    return warnings


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check Telegram strategy plan for stale provider, language, and URL values."
    )
    parser.add_argument(
        "--plan",
        type=Path,
        default=DEFAULT_PLAN_PATH,
        help=f"Plan path to inspect. Defaults to {DEFAULT_PLAN_PATH}.",
    )
    parser.add_argument(
        "--fail-on-warning",
        action="store_true",
        help="Exit with status 1 when content warnings are detected.",
    )
    args = parser.parse_args()

    plan_path = args.plan
    if not plan_path.exists():
        parser.error(f"plan file not found: {plan_path}")

    warnings = iter_plan_content_warnings(plan_path.read_text(encoding="utf-8"))
    if not warnings:
        print("OK: Telegram plan content matches provider/language/url guardrails.")
        print(f"Plan: {plan_path}")
        return 0

    print("WARNING: Telegram plan content drift detected.")
    print(f"Plan: {plan_path}")
    for warning in warnings:
        print(
            f"{warning.line_number}: {warning.category}: "
            f"{warning.detail} :: {warning.text}"
        )
    return 1 if args.fail_on_warning else 0


if __name__ == "__main__":
    raise SystemExit(main())
