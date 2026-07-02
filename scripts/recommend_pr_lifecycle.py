"""Recommend PR lifecycle labels and review order from PR metadata.

This script is intentionally conservative: it does not merge, close, or edit a
PR. It emits a machine-readable label list plus a Markdown comment that a
workflow can post back to the PR.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

try:
    from scripts.check_pr_review_template import validate_pr_body
except ModuleNotFoundError:  # pragma: no cover - supports direct script execution
    from check_pr_review_template import validate_pr_body


DEFAULT_MAIN_BRANCHES = {"main", "master"}
COMMENT_MARKER = "<!-- pr-lifecycle-recommendation -->"

KNOWN_LIFECYCLE_LABELS = [
    "pr-gate:passed",
    "pr-gate:failed",
    "decision:safe-to-merge-candidate",
    "decision:needs-review",
    "decision:needs-tests",
    "decision:merge-after-parent",
    "decision:possible-duplicate",
    "decision:stale-or-superseded",
    "decision:should-close-candidate",
    "source:ai",
    "source:dependabot",
    "risk:runtime",
    "risk:docs-only",
    "risk:tests-only",
    "risk:deps",
    "risk:unknown",
    "domain:contract",
    "domain:rbac",
    "domain:realtime",
    "domain:notifications",
    "domain:queue",
    "domain:registrar",
]


@dataclass(frozen=True)
class PullRequestContext:
    number: int | None
    title: str
    body: str
    base_ref: str
    head_ref: str
    html_url: str
    is_draft: bool
    mergeable: str | None
    author_login: str
    files: tuple[str, ...]


@dataclass(frozen=True)
class Recommendation:
    decisions: tuple[str, ...]
    risk_labels: tuple[str, ...]
    domain_labels: tuple[str, ...]
    source_labels: tuple[str, ...]
    gate_passed: bool
    gate_errors: tuple[str, ...]
    reasons: tuple[str, ...]
    next_actions: tuple[str, ...]

    @property
    def labels(self) -> tuple[str, ...]:
        gate_label = "pr-gate:passed" if self.gate_passed else "pr-gate:failed"
        decision_labels = tuple(f"decision:{decision}" for decision in self.decisions)
        return (
            gate_label,
            *decision_labels,
            *self.source_labels,
            *self.risk_labels,
            *self.domain_labels,
        )


def _read_json(path: str | None) -> dict:
    if not path:
        return {}
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def _collect_files(files_json: dict) -> tuple[str, ...]:
    files = files_json.get("files", [])
    paths: list[str] = []
    for item in files:
        if isinstance(item, str):
            paths.append(item)
        elif isinstance(item, dict) and item.get("path"):
            paths.append(str(item["path"]))
    return tuple(paths)


def _event_to_context(event: dict, files: tuple[str, ...]) -> PullRequestContext:
    pr = event.get("pull_request") or event
    base = pr.get("base") or {}
    head = pr.get("head") or {}
    user = pr.get("user") or pr.get("author") or {}
    return PullRequestContext(
        number=pr.get("number"),
        title=pr.get("title") or "",
        body=pr.get("body") or "",
        base_ref=base.get("ref") or pr.get("baseRefName") or "",
        head_ref=head.get("ref") or pr.get("headRefName") or "",
        html_url=pr.get("html_url") or pr.get("url") or "",
        is_draft=bool(pr.get("draft")),
        mergeable=pr.get("mergeable"),
        author_login=user.get("login") or user.get("name") or "",
        files=files,
    )


def _all_match(paths: Iterable[str], prefixes: tuple[str, ...], suffixes: tuple[str, ...]) -> bool:
    normalized = tuple(path.replace("\\", "/") for path in paths)
    if not normalized:
        return False
    return all(path.startswith(prefixes) or path.endswith(suffixes) for path in normalized)


def _any_file(paths: Iterable[str], prefixes: tuple[str, ...], names: tuple[str, ...]) -> bool:
    for raw_path in paths:
        path = raw_path.replace("\\", "/")
        leaf = path.rsplit("/", 1)[-1]
        if path.startswith(prefixes) or leaf in names:
            return True
    return False


def _contains_any(haystack: str, needles: tuple[str, ...]) -> bool:
    value = haystack.lower()
    return any(needle in value for needle in needles)


def _is_dependabot_pr(ctx: PullRequestContext) -> bool:
    author = ctx.author_login.strip().lower()
    return author in {"app/dependabot", "dependabot[bot]"} or ctx.head_ref.startswith(
        "dependabot/"
    )


def _is_ai_pr(ctx: PullRequestContext) -> bool:
    text = " ".join((ctx.title, ctx.body, ctx.head_ref)).lower()
    markers = ("ai-generated", "jules", "codex", "claude")
    return any(marker in text for marker in markers) or bool(re.search(r"\bv0\b", text))


def _is_possible_duplicate(ctx: PullRequestContext) -> bool:
    text = " ".join((ctx.title, ctx.body, ctx.head_ref)).lower()
    return _contains_any(
        text,
        (
            "duplicate",
            "possible duplicate",
            "supersedes",
            "superseded by",
            "replaces #",
            "same as #",
        ),
    )


def _has_explicit_validation_proof(ctx: PullRequestContext) -> bool:
    validation = validate_pr_body(ctx.body)
    if validation.errors:
        return False

    body = ctx.body.lower()
    proof_terms = ("pytest", "npm test", "npm run test", "smoke", "build", "passed", "green")
    return "## validation" in body and any(term in body for term in proof_terms)


def classify_risk(ctx: PullRequestContext) -> tuple[tuple[str, ...], tuple[str, ...]]:
    files = ctx.files
    text = " ".join((ctx.title, ctx.body, " ".join(files))).lower()

    docs_only = _all_match(files, ("docs/", ".github/ISSUE_TEMPLATE/"), (".md", ".mdx", ".txt"))
    tests_only = not docs_only and _all_match(
        files,
        ("test", "tests/", "backend/tests/", "frontend/src/__tests__/"),
        (".md", ".mdx"),
    )
    deps = (
        _is_dependabot_pr(ctx)
        or _contains_any(ctx.title, ("deps(", "dependency", "lockfile"))
        or _any_file(
            files,
            tuple(),
            (
                "package.json",
                "package-lock.json",
                "pnpm-lock.yaml",
                "yarn.lock",
                "requirements.txt",
                "requirements-dev.txt",
                "pyproject.toml",
                "poetry.lock",
            ),
        )
    )
    runtime = _any_file(
        files,
        (
            "backend/app/",
            "frontend/src/",
            "alembic/",
            "ops/",
            ".github/workflows/",
        ),
        tuple(),
    )

    risk_labels: list[str] = []
    if runtime:
        risk_labels.append("risk:runtime")
    if docs_only:
        risk_labels.append("risk:docs-only")
    if tests_only:
        risk_labels.append("risk:tests-only")
    if deps:
        risk_labels.append("risk:deps")
    if not risk_labels:
        risk_labels.append("risk:unknown")

    domain_map = {
        "domain:contract": ("contract", "endpoint", "payload", "api", "websocket", "ws"),
        "domain:rbac": ("rbac", "role", "permission", "403", "auth"),
        "domain:realtime": ("websocket", "ws", "realtime", "unread", "read-state", "chat"),
        "domain:notifications": ("notification", "telegram", "inbox", "quiet hours"),
        "domain:queue": ("queue", "allocator", "diagnostic", "queue_time"),
        "domain:registrar": ("registrar", "wizard", "batch create", "morning assignment"),
    }
    domain_labels = tuple(label for label, needles in domain_map.items() if _contains_any(text, needles))

    return tuple(dict.fromkeys(risk_labels)), domain_labels


def classify_source(ctx: PullRequestContext) -> tuple[str, ...]:
    source_labels: list[str] = []
    if _is_ai_pr(ctx):
        source_labels.append("source:ai")
    if _is_dependabot_pr(ctx):
        source_labels.append("source:dependabot")
    return tuple(dict.fromkeys(source_labels))


def recommend(ctx: PullRequestContext) -> Recommendation:
    validation = validate_pr_body(ctx.body)
    gate_passed = not validation.errors
    risk_labels, domain_labels = classify_risk(ctx)
    source_labels = classify_source(ctx)
    base_is_main = ctx.base_ref in DEFAULT_MAIN_BRANCHES
    runtime_or_deps = "risk:runtime" in risk_labels or "risk:deps" in risk_labels
    ai_runtime_without_validation = (
        "source:ai" in source_labels
        and "risk:runtime" in risk_labels
        and not _has_explicit_validation_proof(ctx)
    )
    docs_or_tests_only = "risk:docs-only" in risk_labels or "risk:tests-only" in risk_labels

    decisions: list[str] = []
    reasons: list[str] = []
    next_actions: list[str] = []

    if not base_is_main:
        decisions.append("merge-after-parent")
        reasons.append(f"Base branch is `{ctx.base_ref}`, so this PR is stacked behind a parent branch.")
        next_actions.append(f"Merge only after `{ctx.base_ref}` lands or is explicitly superseded.")

    if ctx.is_draft:
        decisions.append("needs-review")
        reasons.append("PR is draft, so it should not be considered merge-ready yet.")
        next_actions.append("Mark ready for review only after the author confirms the scope.")

    if _is_possible_duplicate(ctx):
        decisions.append("possible-duplicate")
        reasons.append("PR text indicates it may duplicate or supersede another PR.")
        next_actions.append("Apply label/comment only; close manually after reviewer confirmation.")

    if not gate_passed:
        decisions.append("needs-review")
        reasons.append("PR body does not satisfy the review quality gate.")
        next_actions.append("Fill the required gate sections before review/merge decision.")

    if runtime_or_deps and not gate_passed:
        decisions.append("needs-tests")
        reasons.append("Runtime/dependency change lacks complete validation proof in the PR body.")
        next_actions.append("Add targeted test, smoke, or explicit not-run rationale.")

    if ai_runtime_without_validation:
        decisions.append("needs-review")
        decisions.append("needs-tests")
        reasons.append("AI-authored runtime change lacks explicit validation proof.")
        next_actions.append("Add concrete runtime validation before any merge decision.")

    if not decisions and runtime_or_deps:
        decisions.append("needs-review")
        reasons.append("Runtime/dependency change passed the body gate but still needs human code review.")
        next_actions.append("Review contract/RBAC/runtime impact and wait for required CI checks.")

    if not decisions and docs_or_tests_only:
        decisions.append("safe-to-merge-candidate")
        reasons.append("Docs/tests-only change passed the body gate and is not stacked behind another branch.")
        next_actions.append("Confirm CI status and merge if reviewers agree.")

    if not decisions:
        decisions.append("needs-review")
        reasons.append("Risk classification is not specific enough for automatic safe-to-merge recommendation.")
        next_actions.append("Reviewer should classify scope before merge decision.")

    return Recommendation(
        decisions=tuple(dict.fromkeys(decisions)),
        risk_labels=risk_labels,
        domain_labels=domain_labels,
        source_labels=source_labels,
        gate_passed=gate_passed,
        gate_errors=tuple(validation.errors),
        reasons=tuple(dict.fromkeys(reasons)),
        next_actions=tuple(dict.fromkeys(next_actions)),
    )


def render_comment(ctx: PullRequestContext, rec: Recommendation) -> str:
    decision_text = ", ".join(rec.decisions)
    risk_text = ", ".join(label.removeprefix("risk:") for label in rec.risk_labels)
    source_text = (
        ", ".join(label.removeprefix("source:") for label in rec.source_labels)
        or "none detected"
    )
    domain_text = ", ".join(label.removeprefix("domain:") for label in rec.domain_labels) or "none detected"
    gate_text = "passed" if rec.gate_passed else "failed"
    pr_label = f"PR #{ctx.number}" if ctx.number else "PR"

    lines = [
        COMMENT_MARKER,
        "## PR lifecycle recommendation",
        "",
        f"- PR: {pr_label}",
        f"- Decision: `{decision_text}`",
        f"- Source: `{source_text}`",
        f"- Risk lane: `{risk_text}`",
        f"- Domains: `{domain_text}`",
        f"- Body gate: `{gate_text}`",
        f"- Base/head: `{ctx.base_ref}` <- `{ctx.head_ref}`",
        "",
        "### Why",
    ]
    lines.extend(f"- {reason}" for reason in rec.reasons)
    lines.extend(["", "### Next action"])
    lines.extend(f"- {action}" for action in rec.next_actions)

    if rec.gate_errors:
        lines.extend(["", "### Body gate gaps"])
        lines.extend(f"- {error}" for error in rec.gate_errors[:8])
        if len(rec.gate_errors) > 8:
            lines.append(f"- ...and {len(rec.gate_errors) - 8} more.")

    lines.extend(
        [
            "",
            "### Manual merge decision options",
            "- `safe to merge`: only after CI and reviewer approval.",
            "- `needs review`: default for runtime, contract, RBAC, queue, realtime, or unclear scope.",
            "- `needs tests`: required when validation proof is missing or too broad.",
            "- `stale / superseded`: use when a newer PR replaces this branch.",
            "- `should close`: use only after confirming no useful current work remains.",
            "- `merge only after parent PR`: use for stacked branches or non-main base branches.",
        ]
    )
    return "\n".join(lines) + "\n"


def write_lines(path: str | None, lines: Iterable[str]) -> None:
    if not path:
        return
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--event-file", required=True, help="GitHub event JSON path")
    parser.add_argument("--files-json", required=True, help="JSON from `gh pr view --json files`")
    parser.add_argument("--output-comment", required=True, help="Markdown comment output path")
    parser.add_argument("--output-labels", required=True, help="Labels output path, one label per line")
    parser.add_argument(
        "--output-known-labels",
        help="Optional known lifecycle labels output path for workflow cleanup",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    event = _read_json(args.event_file)
    files_json = _read_json(args.files_json)
    ctx = _event_to_context(event, _collect_files(files_json))
    rec = recommend(ctx)

    Path(args.output_comment).write_text(render_comment(ctx, rec), encoding="utf-8")
    write_lines(args.output_labels, rec.labels)
    write_lines(args.output_known_labels, KNOWN_LIFECYCLE_LABELS)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
