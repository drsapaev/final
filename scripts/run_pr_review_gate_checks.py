#!/usr/bin/env python3
"""Run all lightweight PR review gate checks with stdlib Python only."""

from __future__ import annotations

import argparse
import os
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLE_BODY_FILES = (
    REPO_ROOT / "docs" / "runbooks" / "pr-review-samples" / "docs-only-pr.md",
    REPO_ROOT / "docs" / "runbooks" / "pr-review-samples" / "runtime-contract-pr.md",
)
DEPENDABOT_AUTHORS = {"app/dependabot", "dependabot[bot]"}


def _ensure_repo_imports() -> None:
    repo_root_text = str(REPO_ROOT)
    if repo_root_text not in sys.path:
        sys.path.insert(0, repo_root_text)


def _run_unit_tests() -> bool:
    _ensure_repo_imports()
    # PR #1781 moved the root test_*.py files to scripts/legacy_tests/root/.
    # Add that directory to sys.path so the legacy test module names resolve.
    legacy_tests_root = REPO_ROOT / "scripts" / "legacy_tests" / "root"
    legacy_tests_text = str(legacy_tests_root)
    if legacy_tests_text not in sys.path:
        sys.path.insert(0, legacy_tests_text)
    suite = unittest.defaultTestLoader.loadTestsFromNames(
        [
            "test_check_pr_review_template",
            "test_add_pr_review_adoption_entry",
            "test_run_pr_review_gate_checks",
        ]
    )
    result = unittest.TextTestRunner(stream=sys.stdout, verbosity=2).run(suite)
    return result.wasSuccessful()


def _validate_body(label: str, body: str) -> bool:
    _ensure_repo_imports()
    from scripts.check_pr_review_template import validate_pr_body

    print(f"\nValidating {label}...")
    result = validate_pr_body(body)
    for warning in result.warnings:
        print(f"warning: {warning}")

    if result.errors:
        print(f"{label} failed:")
        for error in result.errors:
            print(f"- {error}")
        return False

    print(f"{label} passed.")
    return True


def _validate_sample_bodies() -> bool:
    ok = True
    for sample_path in SAMPLE_BODY_FILES:
        if not sample_path.exists():
            print(f"missing sample body: {sample_path}")
            ok = False
            continue
        ok = _validate_body(
            str(sample_path.relative_to(REPO_ROOT)),
            sample_path.read_text(encoding="utf-8"),
        ) and ok
    return ok


def _read_pr_body(args: argparse.Namespace) -> tuple[str, str] | None:
    if args.body_env:
        return f"env:{args.body_env}", os.environ.get(args.body_env, "")
    if args.body_file:
        path = Path(args.body_file)
        return str(path), path.read_text(encoding="utf-8")
    return None


def _read_pr_author(args: argparse.Namespace) -> str:
    if args.author:
        return args.author
    if args.author_env:
        return os.environ.get(args.author_env, "")
    return os.environ.get("PR_AUTHOR", "")


def _is_dependabot_author(author: str) -> bool:
    return author.strip().lower() in DEPENDABOT_AUTHORS


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run PR review gate unit tests, samples, and optional PR body validation."
    )
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--body-file", help="Path to a markdown file containing PR body.")
    source.add_argument("--body-env", help="Environment variable containing PR body text.")
    parser.add_argument("--author", help="Pull request author login.")
    parser.add_argument("--author-env", help="Environment variable containing the PR author login.")
    args = parser.parse_args()

    ok = True
    print("Running PR review gate unit tests...")
    ok = _run_unit_tests() and ok

    print("\nValidating documented sample PR bodies...")
    ok = _validate_sample_bodies() and ok

    pr_body = _read_pr_body(args)
    if pr_body:
        label, body = pr_body
        author = _read_pr_author(args)
        if _is_dependabot_author(author):
            print(
                f"\nSkipping live PR body validation for Dependabot author `{author}`; "
                "Dependabot bodies are generated release notes, not the human review template."
            )
        else:
            ok = _validate_body(label, body) and ok
    else:
        print("\nNo live PR body provided; skipped live PR body validation.")

    if not ok:
        print("\nPR review gate checks failed.")
        return 1

    print("\nPR review gate checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
