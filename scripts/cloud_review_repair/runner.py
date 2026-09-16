"""Ephemeral cloud review runner; never intended for the product branch."""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["prepare", "validate", "publish"])
    args = parser.parse_args()
    control = Path(os.environ["GITHUB_WORKSPACE"])
    work = Path(os.environ["RUNNER_TEMP"]) / "product"
    evidence = Path(os.environ["RUNNER_TEMP"]) / "evidence"
    evidence.mkdir(exist_ok=True)
    cfg = json.loads((control / "scripts/cloud_review_repair/config.json").read_text())
    branch = cfg["branch"]
    assert re.fullmatch(r"fix/review-[a-z0-9-]+", branch), branch
    source_ref = cfg.get("source_ref", "main")
    assert source_ref == "main" or source_ref == branch
    task_rel = cfg["task"]
    assert re.fullmatch(r"scripts/cloud_review_repair/tasks/[a-z0-9_-]+\.py", task_rel)
    task = control / task_rel
    allowed = set(cfg["allowed_paths"])
    assert allowed and all(not p.startswith(("/", ".git/", ".github/")) and ".." not in p.split("/") for p in allowed)

    def run(cmd: list[str], label: str, *, cwd: Path = work, expected: int = 0) -> subprocess.CompletedProcess:
        print(f"\n=== {label}: {cmd!r} ===", flush=True)
        result = subprocess.run(cmd, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        output = result.stdout
        (evidence / f"{label}.log").write_text(output)
        print(output, flush=True)
        if result.returncode != expected:
            raise RuntimeError(f"{label}: expected exit {expected}, received {result.returncode}")
        return result

    if args.phase == "prepare":
        run(["git", "fetch", "--depth=1", "origin", source_ref], "fetch", cwd=control)
        run(["git", "worktree", "add", "--detach", str(work), "FETCH_HEAD"], "worktree", cwd=control)
        base = run(["git", "rev-parse", "HEAD"], "base-sha").stdout.strip()
        (evidence / "base-sha.txt").write_text(base + "\n")
        assert not run(["git", "status", "--porcelain"], "initial-status").stdout.strip()
        return

    if args.phase == "validate":
        for i, command in enumerate(cfg.get("post_merge_checks", [])):
            run(command["argv"], f"post-merge-{i}", cwd=work / command.get("cwd", ""))
        # Create regression files first so the path-aware gate sees new test
        # paths too. No production source is modified before this gate.
        run([sys.executable, str(task), "tests"], "prepare-tests")
        gate = work / "ai/langgraph/scripts/run_agent_gate.ps1"
        gate_result = run(["pwsh", "-NoProfile", "-File", str(gate), cfg["question"], "--known-root-cause", cfg["root_cause"]], "gate")
        gate_data = json.loads(next(line for line in gate_result.stdout.splitlines() if line.startswith("{")))
        assert gate_data["result"] == "gate_ok", gate_data
        assert set(gate_data["first_touch_files"]) == allowed, gate_data
        red = cfg.get("red")
        if red:
            argv = [v.replace("$EVIDENCE", str(evidence)) for v in red["argv"]]
            run(argv, "red", cwd=work / red.get("cwd", ""), expected=1)
            tree = ET.parse(evidence / "red.xml")
            cases = tree.findall(".//testcase")
            failures = tree.findall(".//failure")
            assert len(failures) == red["failures"], (len(failures), red["failures"])
            assert not tree.findall(".//error"), "RED must be behavioral assertion failures, not broken setup"
            assert not tree.findall(".//skipped"), "RED selection must not skip"
            (evidence / "red-proof.txt").write_text(f"cases={len(cases)}; assertion_failures={len(failures)}; errors=0; skips=0\n")
        run([sys.executable, str(task), "fix"], "apply-fix")
        for i, command in enumerate(cfg["green"]):
            argv = [v.replace("$EVIDENCE", str(evidence)) for v in command["argv"]]
            run(argv, f"green-{i}", cwd=work / command.get("cwd", ""))
        run(["git", "diff", "--check"], "diff-check")
        run(["git", "add", "--intent-to-add", "--", *sorted(allowed)], "intent-to-add")
        actual = set(run(["git", "diff", "--name-only"], "changed-paths").stdout.splitlines())
        assert actual and actual <= allowed, actual - allowed
        assert not run(["git", "ls-files", "--others", "--exclude-standard"], "untracked-check").stdout.strip()
        run(["git", "diff", "--check"], "complete-diff-check")
        run(["git", "diff", "--stat"], "diffstat")
        patch = subprocess.check_output(["git", "diff"], cwd=work)
        (evidence / "product.patch").write_bytes(patch)
        (evidence / "validated.json").write_text(json.dumps({"branch": branch, "paths": sorted(actual), "base": (evidence / "base-sha.txt").read_text().strip()}))
        return

    validated = json.loads((evidence / "validated.json").read_text())
    assert validated["branch"] == branch
    run(["git", "config", "user.name", "github-actions[bot]"], "git-name")
    run(["git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com"], "git-email")
    run(["git", "switch", "-c", branch], "feature-branch")
    run(["git", "add", "--", *validated["paths"]], "stage")
    run(["git", "commit", "-m", cfg["commit_message"]], "commit")
    run(["gh", "auth", "setup-git"], "git-auth")
    run(["git", "push", "origin", f"HEAD:refs/heads/{branch}"], "publish")
    sha = run(["git", "rev-parse", "HEAD"], "commit-sha").stdout.strip()
    (evidence / "commit-sha.txt").write_text(sha + "\n")


if __name__ == "__main__":
    main()
