"""Warn when Telegram runtime changes are missing the Telegram strategy plan.

Default behavior is warning-only. Use ``--fail-on-warning`` when wiring this
into CI or a release gate.
"""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


PLAN_PATH = ".ai-factory/plans/telegram-bot-clinic-full-strategy.md"
TELEGRAM_RUNTIME_PREFIXES = (
    "backend/app/api/v1/endpoints/admin_telegram.py",
    "backend/app/api/v1/endpoints/telegram_",
    "backend/app/services/telegram_",
    "backend/app/models/telegram_",
    "backend/app/schemas/telegram_",
    "backend/tests/unit/test_telegram_",
    "frontend/src/components/Telegram",
)


def _normalize(path: str) -> str:
    normalized = Path(path).as_posix()
    if normalized.startswith("./"):
        return normalized[2:]
    return normalized


def _git_changed_files(base: str, head: str) -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--name-only", "--diff-filter=ACMR", f"{base}...{head}"],
        check=True,
        capture_output=True,
        text=True,
    )
    return [_normalize(line) for line in result.stdout.splitlines() if line.strip()]


def _is_telegram_runtime_file(path: str) -> bool:
    normalized = _normalize(path)
    return any(normalized.startswith(prefix) for prefix in TELEGRAM_RUNTIME_PREFIXES)


def check_plan_drift(changed_files: list[str]) -> tuple[bool, list[str]]:
    normalized = [_normalize(path) for path in changed_files]
    plan_changed = PLAN_PATH in normalized
    telegram_runtime_files = [
        path for path in normalized if _is_telegram_runtime_file(path)
    ]
    return bool(telegram_runtime_files and not plan_changed), telegram_runtime_files


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Warn when Telegram runtime files changed without the strategy plan."
    )
    parser.add_argument("--base", default="origin/main", help="Git diff base.")
    parser.add_argument("--head", default="HEAD", help="Git diff head.")
    parser.add_argument(
        "--changed-file",
        action="append",
        default=[],
        help="Synthetic changed file. Repeat to bypass git diff for tests/smoke.",
    )
    parser.add_argument(
        "--fail-on-warning",
        action="store_true",
        help="Exit with status 1 when drift is detected.",
    )
    args = parser.parse_args()

    changed_files = (
        [_normalize(path) for path in args.changed_file]
        if args.changed_file
        else _git_changed_files(args.base, args.head)
    )

    drift_detected, telegram_runtime_files = check_plan_drift(changed_files)
    if drift_detected:
        print("WARNING: Telegram runtime files changed without strategy plan update.")
        print(f"Plan path: {PLAN_PATH}")
        print("Runtime files:")
        for path in telegram_runtime_files:
            print(f"- {path}")
        return 1 if args.fail_on_warning else 0

    if telegram_runtime_files:
        print("OK: Telegram runtime changes include the strategy plan.")
    else:
        print("OK: no Telegram runtime file changes detected.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
