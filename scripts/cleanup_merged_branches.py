#!/usr/bin/env python3
"""Clean up local task branches after the PR lifecycle is complete.

Default mode is dry-run. The script only deletes branches with explicit
evidence that they are already merged into the base branch, or that GitHub says
their PR is MERGED. Branches checked out by any worktree are always kept.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Sequence


DEFAULT_BASE = "origin/main"
DEFAULT_PROTECTED_BRANCHES = ("main", "master", "develop", "staging", "production")
PR_BRANCH_RE = re.compile(r"^pr[-_/](?P<number>\d+)$", re.IGNORECASE)


class Evidence(str, Enum):
    GRAPH_MERGED = "graph-merged"
    GITHUB_MERGED = "github-merged"


@dataclass(frozen=True)
class DeleteCandidate:
    branch: str
    evidence: Evidence
    detail: str


@dataclass(frozen=True)
class KeptBranch:
    branch: str
    reason: str


@dataclass(frozen=True)
class CleanupPlan:
    candidates: tuple[DeleteCandidate, ...]
    kept: tuple[KeptBranch, ...]


@dataclass(frozen=True)
class LocalBaseStatus:
    branch: str
    base: str
    ahead: int
    behind: int
    worktree_path: str | None
    clean: bool | None
    detail: str


def run_command(args: Sequence[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        check=check,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )


def git_lines(args: Sequence[str]) -> tuple[str, ...]:
    result = run_command(("git", *args))
    return tuple(line.strip() for line in result.stdout.splitlines() if line.strip())


def list_local_branches() -> tuple[str, ...]:
    return git_lines(("for-each-ref", "--format=%(refname:short)", "refs/heads"))


def list_graph_merged_branches(base: str) -> tuple[str, ...]:
    return git_lines(
        ("for-each-ref", f"--merged={base}", "--format=%(refname:short)", "refs/heads")
    )


def parse_worktree_branches(porcelain: str) -> frozenset[str]:
    return frozenset(parse_worktree_branch_paths(porcelain))


def parse_worktree_branch_paths(porcelain: str) -> dict[str, str]:
    paths: dict[str, str] = {}
    current_path: str | None = None
    prefix = "branch refs/heads/"
    for raw_line in porcelain.splitlines():
        line = raw_line.strip()
        if line.startswith("worktree "):
            current_path = line.removeprefix("worktree ")
            continue
        if line.startswith(prefix) and current_path:
            paths[line.removeprefix(prefix)] = current_path
    return paths


def is_protected_branch(branch: str, protected: Iterable[str]) -> bool:
    protected_set = set(protected)
    return (
        branch in protected_set
        or branch.startswith("release/")
        or branch.startswith("hotfix/")
        or branch.startswith("protected/")
    )


def parse_pr_number_from_branch(branch: str) -> int | None:
    match = PR_BRANCH_RE.match(branch)
    if not match:
        return None
    return int(match.group("number"))


def local_branch_for_base(base: str) -> str | None:
    if base.startswith("origin/") and base.count("/") == 1:
        return base.split("/", 1)[1]
    return None


def parse_ahead_behind(stdout: str) -> tuple[int, int]:
    parts = stdout.strip().split()
    if len(parts) != 2:
        raise ValueError(f"unexpected rev-list output: {stdout!r}")
    ahead, behind = parts
    return int(ahead), int(behind)


def worktree_is_clean(path: str) -> bool:
    result = run_command(("git", "-C", path, "status", "--porcelain"))
    return not result.stdout.strip()


def inspect_local_base_status(
    *,
    base: str,
    branches: Iterable[str],
    worktree_branch_paths: dict[str, str],
) -> LocalBaseStatus | None:
    local_branch = local_branch_for_base(base)
    if not local_branch or local_branch not in set(branches):
        return None

    result = run_command(
        ("git", "rev-list", "--left-right", "--count", f"{local_branch}...{base}")
    )
    ahead, behind = parse_ahead_behind(result.stdout)
    path = worktree_branch_paths.get(local_branch)
    clean = worktree_is_clean(path) if path else None

    if ahead:
        detail = f"local {local_branch} has {ahead} commit(s) not in {base}; manual review required"
    elif behind:
        detail = f"local {local_branch} is behind {base} by {behind} commit(s)"
    else:
        detail = f"local {local_branch} is aligned with {base}"

    if path and clean is False:
        detail += "; worktree has uncommitted changes"

    return LocalBaseStatus(
        branch=local_branch,
        base=base,
        ahead=ahead,
        behind=behind,
        worktree_path=path,
        clean=clean,
        detail=detail,
    )


def sync_local_base(status: LocalBaseStatus) -> None:
    if status.ahead:
        raise RuntimeError(status.detail)
    if not status.behind:
        print(f"local {status.branch} already aligned with {status.base}")
        return

    if status.worktree_path:
        if status.clean is False:
            raise RuntimeError(status.detail)
        run_command(("git", "-C", status.worktree_path, "merge", "--ff-only", status.base))
    else:
        run_command(("git", "branch", "-f", status.branch, status.base))
    print(f"fast-forwarded local {status.branch} to {status.base}")


def parse_gh_pr_list(stdout: str) -> tuple[dict, ...]:
    if not stdout.strip():
        return ()
    payload = json.loads(stdout)
    if not isinstance(payload, list):
        return ()
    return tuple(item for item in payload if isinstance(item, dict))


def branch_has_merged_pr(branch: str, *, repo: str | None) -> str | None:
    base_args = ["gh", "pr", "list", "--state", "all", "--head", branch]
    if repo:
        base_args.extend(["--repo", repo])
    base_args.extend(["--json", "number,state,mergedAt,title", "--limit", "5"])

    result = run_command(base_args, check=False)
    if result.returncode == 0:
        for pr in parse_gh_pr_list(result.stdout):
            if pr.get("state") == "MERGED" and pr.get("mergedAt"):
                title = pr.get("title") or ""
                return f"PR #{pr.get('number')} merged at {pr.get('mergedAt')}: {title}"

    pr_number = parse_pr_number_from_branch(branch)
    if pr_number is None:
        return None

    view_args = ["gh", "pr", "view", str(pr_number)]
    if repo:
        view_args.extend(["--repo", repo])
    view_args.extend(["--json", "number,state,mergedAt,title"])
    view = run_command(view_args, check=False)
    if view.returncode != 0 or not view.stdout.strip():
        return None

    pr = json.loads(view.stdout)
    if pr.get("state") == "MERGED" and pr.get("mergedAt"):
        title = pr.get("title") or ""
        return f"PR #{pr.get('number')} merged at {pr.get('mergedAt')}: {title}"
    return None


def build_cleanup_plan(
    *,
    branches: Iterable[str],
    graph_merged: Iterable[str],
    active_worktree_branches: Iterable[str],
    protected_branches: Iterable[str],
    repo: str | None,
    include_github: bool,
) -> CleanupPlan:
    active = set(active_worktree_branches)
    merged = set(graph_merged)

    candidates: list[DeleteCandidate] = []
    kept: list[KeptBranch] = []
    seen_candidates: set[str] = set()

    for branch in sorted(set(branches)):
        if branch in active:
            kept.append(KeptBranch(branch, "checked out by an active worktree"))
            continue
        if is_protected_branch(branch, protected_branches):
            kept.append(KeptBranch(branch, "protected branch name"))
            continue
        if branch in merged:
            candidates.append(
                DeleteCandidate(
                    branch=branch,
                    evidence=Evidence.GRAPH_MERGED,
                    detail="reachable from base branch commit graph",
                )
            )
            seen_candidates.add(branch)
            continue

        if include_github:
            detail = branch_has_merged_pr(branch, repo=repo)
            if detail:
                candidates.append(
                    DeleteCandidate(
                        branch=branch,
                        evidence=Evidence.GITHUB_MERGED,
                        detail=detail,
                    )
                )
                seen_candidates.add(branch)
                continue

        if branch not in seen_candidates:
            kept.append(KeptBranch(branch, "no merged evidence found"))

    return CleanupPlan(candidates=tuple(candidates), kept=tuple(kept))


def print_plan(
    plan: CleanupPlan,
    *,
    base: str,
    delete: bool,
    local_base_status: LocalBaseStatus | None,
) -> None:
    mode = "delete" if delete else "dry-run"
    print(f"Branch lifecycle cleanup ({mode})")
    print(f"base: {base}")
    print()

    print("Local base freshness:")
    if not local_base_status:
        print("- skipped: base is not an origin/<branch> ref or local branch is absent")
    else:
        print(f"- {local_base_status.detail}")
        if local_base_status.behind and not local_base_status.ahead:
            print("- run with --sync-local-base to fast-forward it")
    print()

    print("Delete candidates:")
    if not plan.candidates:
        print("- none")
    for candidate in plan.candidates:
        print(f"- {candidate.branch} [{candidate.evidence.value}] {candidate.detail}")

    print()
    print("Kept branches:")
    if not plan.kept:
        print("- none")
    for kept in plan.kept:
        print(f"- {kept.branch}: {kept.reason}")


def delete_candidates(candidates: Iterable[DeleteCandidate]) -> None:
    for candidate in candidates:
        flag = "-d" if candidate.evidence is Evidence.GRAPH_MERGED else "-D"
        run_command(("git", "branch", flag, candidate.branch))
        print(f"deleted {candidate.branch} ({candidate.evidence.value})")


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default=DEFAULT_BASE, help=f"Base ref, default: {DEFAULT_BASE}")
    parser.add_argument("--repo", help="GitHub repo in owner/name form for PR status checks.")
    parser.add_argument(
        "--protected",
        action="append",
        default=[],
        help="Additional protected local branch name. Can be passed multiple times.",
    )
    parser.add_argument("--delete", action="store_true", help="Delete candidates instead of dry-run.")
    parser.add_argument("--no-fetch", action="store_true", help="Skip `git fetch --prune origin`.")
    parser.add_argument(
        "--no-github",
        action="store_true",
        help="Do not query GitHub for squash/rebase-merged PR evidence.",
    )
    parser.add_argument(
        "--prune-worktrees",
        action="store_true",
        help="Run `git worktree prune` before branch analysis.",
    )
    parser.add_argument(
        "--sync-local-base",
        action="store_true",
        help="Fast-forward the local base branch, for example main -> origin/main, when safe.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])

    if not args.no_fetch:
        run_command(("git", "fetch", "--prune", "origin"))
    if args.prune_worktrees:
        run_command(("git", "worktree", "prune"))

    branches = list_local_branches()
    graph_merged = list_graph_merged_branches(args.base)
    worktree = run_command(("git", "worktree", "list", "--porcelain"))
    worktree_branch_paths = parse_worktree_branch_paths(worktree.stdout)
    active = frozenset(worktree_branch_paths)
    protected = (*DEFAULT_PROTECTED_BRANCHES, *args.protected)
    local_base_status = inspect_local_base_status(
        base=args.base,
        branches=branches,
        worktree_branch_paths=worktree_branch_paths,
    )

    if args.sync_local_base and local_base_status:
        sync_local_base(local_base_status)
        branches = list_local_branches()
        graph_merged = list_graph_merged_branches(args.base)
        local_base_status = inspect_local_base_status(
            base=args.base,
            branches=branches,
            worktree_branch_paths=worktree_branch_paths,
        )

    plan = build_cleanup_plan(
        branches=branches,
        graph_merged=graph_merged,
        active_worktree_branches=active,
        protected_branches=protected,
        repo=args.repo,
        include_github=not args.no_github,
    )
    print_plan(plan, base=args.base, delete=args.delete, local_base_status=local_base_status)

    if args.delete:
        print()
        delete_candidates(plan.candidates)
    elif plan.candidates:
        print()
        print("Dry-run only. Re-run with --delete to remove delete candidates.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
