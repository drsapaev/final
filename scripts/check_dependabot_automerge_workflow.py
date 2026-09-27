#!/usr/bin/env python3
"""Repeatable tests for .github/workflows/dependabot-automerge.yml.

Locks the managed-Dependabot protective logic (#3495/#3500 reviews):

  1. Structural assertions on the workflow YAML (triggers, steps,
     fail-closed patterns - e.g. the disable step must NOT suppress
     errors of "gh pr merge --disable-auto").
  2. Behavioral tests that extract the REAL run scripts from the YAML
     and execute them under bash with a stateful stub "gh" on PATH -
     so a future edit that reintroduces fail-open behavior fails here.

Run: python scripts/check_dependabot_automerge_workflow.py
CI:  .github/workflows/dependabot-guard-tests.yml (paths-filtered).
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.exit("PyYAML is required: pip install pyyaml")

REPO = Path(__file__).resolve().parents[1]
WORKFLOW = REPO / ".github" / "workflows" / "dependabot-automerge.yml"

FAILURES: list[str] = []
CHECKS = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global CHECKS
    CHECKS += 1
    if cond:
        print(f"  ok  {name}")
    else:
        FAILURES.append(f"{name}" + (f" :: {detail}" if detail else ""))
        print(f" FAIL {name}" + (f" :: {detail}" if detail else ""))


def load_steps() -> dict[str, str]:
    """Map step id/name -> run script body, straight from the YAML."""
    data = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    trigger = data[True] if True in data else data["on"]
    steps = data["jobs"]["classify-and-route"]["steps"]
    # Windows checkouts carry CRLF; GitHub runners execute LF. Normalize
    # exactly what a runner would see before any bash execution.
    return trigger, {
        s.get("id") or s.get("name"): (s.get("run") or "").replace("\r\n", "\n").replace("\r", "\n")
        for s in steps
    }


def bash_n(script: str) -> bool:
    # Bytes input: text mode would translate \n -> \r\n on Windows stdin.
    r = subprocess.run([BASH, "-n"], input=script.encode("utf-8"), capture_output=True)
    return r.returncode == 0


# --- behavioral harness ------------------------------------------------------

STUB_GH = r"""#!/usr/bin/env bash
# Stateful gh stub: behavior driven by GHSTUB_* env vars, every call logged.
printf '%s\n' "$*" >> "${GHSTUB_LOG:?}"
if [ "$1" = "api" ]; then
  case "$2" in
    */pulls/*/files)
      if [ "${GHSTUB_FILES_API_FAILS:-0}" = "1" ]; then
        echo "stub: files api error" >&2; exit 1
      fi
      cat "${GHSTUB_FILES:?}"; exit 0 ;;
    */pulls/*)
      if [ "${GHSTUB_STATE_API_FAILS:-0}" = "1" ]; then
        echo "stub: state api error" >&2; exit 1
      fi
      cat "${GHSTUB_AM_STATE:?}"; exit 0 ;;
  esac
  exit 0
fi
case "$1 $2 $3" in
  "pr merge --disable-auto")
    if [ "${GHSTUB_DISABLE_FAILS:-0}" = "1" ]; then
      echo "stub: disable failed" >&2; exit 1
    fi
    if [ "${GHSTUB_DISABLE_IGNORING:-0}" != "1" ]; then
      : > "${GHSTUB_AM_STATE:?}"
    fi
    exit 0 ;;
  "pr merge --auto")
    if [ "${GHSTUB_AUTO_FAILS:-0}" = "1" ]; then exit 1; fi
    exit 0 ;;
esac
exit 0
"""


def _find_bash() -> str | None:
    """Locate a real bash. On Windows, shutil.which('bash') can resolve to
    System32\\bash.exe (the WSL launcher), which drops every env var not
    listed in WSLENV - unusable here. Prefer Git Bash explicitly."""
    if os.name != "nt":
        return shutil.which("bash")
    git_bash = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Git" / "usr" / "bin" / "bash.exe"
    if git_bash.exists():
        return str(git_bash)
    found = shutil.which("bash") or ""
    if found and "system32" not in found.lower():
        return found
    return None


BASH = _find_bash()


def run_step(script: str, stub_env: dict[str, str], outputs_env: dict[str, str]) -> dict:
    """Execute a workflow step script under bash with the stub gh on PATH.

    Everything runs with cwd inside the scratch dir and RELATIVE paths
    only (bin/, step.sh, scratch files) - Windows-path argv breaks MSYS
    bash, and absolute POSIX conversion depends on mounts. The dir is
    removed with retries: a just-exited bash may still hold its cwd.
    """
    root = Path(tempfile.mkdtemp(prefix="depbot_guard_"))
    try:
        stub_dir = root / "bin"
        stub_dir.mkdir()
        (stub_dir / "gh").write_text(STUB_GH, newline="\n")
        os.chmod(stub_dir / "gh", 0o755)

        out_file = root / "github_output.txt"
        log_file = root / "gh_calls.log"
        am_state = root / "am_state.txt"
        files_list = root / "files.txt"
        for f, content in (
            (am_state, stub_env.get("_AM_STATE", "")),
            (files_list, stub_env.get("_FILES", "")),
        ):
            f.write_text(content, newline="\n")

        env = {
            k: v
            for k, v in os.environ.items()
            if not k.startswith("GHSTUB_") and k not in ("GITHUB_OUTPUT", "GITHUB_REPOSITORY")
        }
        env.update(
            GITHUB_OUTPUT="github_output.txt",
            GITHUB_REPOSITORY="test/repo",
            PR="7",
            PR_URL="https://example.test/pr/7",
            REASON="unexpected_files",
            GH_TOKEN="stub-token",
            GHSTUB_LOG="gh_calls.log",
            GHSTUB_AM_STATE="am_state.txt",
            GHSTUB_FILES="files.txt",
        )
        env.update(stub_env)
        env.update(outputs_env)

        (root / "step.sh").write_text(script, newline="\n")
        proc = subprocess.run(
            # GitHub's default shell for run steps is 'bash -e {0}' - simulate it.
            [BASH, "-c", 'export PATH="bin:$PATH"; exec bash -e step.sh'],
            cwd=str(root),
            env=env,
            capture_output=True,
            text=True,
        )

        outputs: dict[str, str] = {}
        if out_file.exists():
            for line in out_file.read_text(encoding="utf-8").splitlines():
                if "=" in line:
                    k, _, v = line.partition("=")
                    outputs[k] = v
        calls = log_file.read_text(encoding="utf-8").splitlines() if log_file.exists() else []
        return {
            "rc": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "outputs": outputs,
            "calls": calls,
            "am_state": am_state.read_text(encoding="utf-8"),
        }
    finally:
        for attempt in range(5):
            try:
                shutil.rmtree(root)
                break
            except OSError:
                time.sleep(0.2 * (attempt + 1))


# --- tests -------------------------------------------------------------------


def test_structure(trigger: dict, steps: dict[str, str]) -> None:
    print("structure:")
    types = trigger["pull_request_target"]["types"]
    check("triggers include synchronize", "synchronize" in types, str(types))
    for key in ("classify", "guard", "decide"):
        check(f"step '{key}' present with script", bool(steps.get(key, "").strip()))
    for name in ("Enable auto-merge", "Fail-closed - disable", "Keep auto-merge", "Route to the manual triage"):
        check(f"step '{name}' present", any(k.startswith(name) for k in steps))

    guard = steps["guard"]
    check("guard: fail-closed api call", "if ! files=$(gh api" in guard)
    check("guard: empty-list branch", 'elif [ -z "$files" ]' in guard)
    check("guard: allowlist applied via grep -vE", 'grep -vE "$allow_re"' in guard)
    api_line = next((ln for ln in guard.splitlines() if "files=$(gh api" in ln), "")
    check("guard: api line not error-suppressed", bool(api_line) and "|| true" not in api_line)

    disable_key = next(k for k in steps if k.startswith("Fail-closed - disable"))
    disable = steps[disable_key]
    check("disable: no suppressed --disable-auto", not re.search(r"gh pr merge --disable-auto[^\n]*\|\|\s*true", disable))
    check("disable: queries .auto_merge state", ".auto_merge // empty" in disable)
    check("disable: state queried BEFORE disable", disable.find("before=$(am_state)") < disable.find("--disable-auto"))
    check("disable: re-verifies after disable", "after=$(am_state)" in disable)
    check("disable: state query failure is fatal", disable.count("exit 1") >= 3)
    check("disable: bash -n clean", bash_n(disable))
    for key in ("classify", "guard", "decide"):
        check(f"{key}: bash -n clean", bash_n(steps[key]))


def test_classify(steps: dict[str, str]) -> None:
    print("classify:")
    cases = [
        ("grouped frontend title", "deps(deps): bump the frontend-npm-minor-patch group across 1 directory with 17 updates", "automerge"),
        ("grouped root title", "deps(deps): bump the root-npm-minor-patch group in / with 3 updates", "automerge"),
        ("security single bump", "deps(deps): bump pillow from 10.1.0 to 10.2.0 in /backend", "triage"),
        ("major single bump", "deps(deps): bump vitest from 3.2.7 to 5.0.0 in /frontend", "triage"),
        ("actions major", "ci(deps): bump actions/setup-node from 4 to 7", "triage"),
    ]
    for label, title, expected in cases:
        r = run_step(steps["classify"], {}, {"TITLE": title})
        check(label, r["rc"] == 0 and r["outputs"].get("verdict") == expected, f"rc={r['rc']} err={r['stderr'][:200]}")


def test_guard(steps: dict[str, str]) -> None:
    print("guard:")
    allowed = "frontend/package.json\nfrontend/package-lock.json\n"
    cases = [
        ("all files allowed", {"_FILES": allowed}, "true", None),
        ("unexpected file fails closed", {"_FILES": allowed + ".github/workflows/evil.yml\n"}, "false", "unexpected_files"),
        ("empty file list fails closed", {"_FILES": ""}, "false", "empty_file_list"),
        ("api error fails closed", {"_FILES": allowed, "GHSTUB_FILES_API_FAILS": "1"}, "false", "api_error"),
    ]
    for label, stub_env, files_ok, reason in cases:
        r = run_step(steps["guard"], stub_env, {})
        out = r["outputs"]
        ok = r["rc"] == 0 and out.get("files_ok") == files_ok
        if reason is not None:
            ok = ok and out.get("reason") == reason
        check(label, ok, f"rc={r['rc']} outputs={out} err={r['stderr'][:200]}")


def test_decide(steps: dict[str, str]) -> None:
    print("decide:")
    cases = [
        ("opened+eligible -> enable", {"VERDICT": "automerge", "FILES_OK": "true", "EVENT": "opened"}, "enable"),
        ("reopened+eligible -> enable", {"VERDICT": "automerge", "FILES_OK": "true", "EVENT": "reopened"}, "enable"),
        ("synchronize+eligible -> none", {"VERDICT": "automerge", "FILES_OK": "true", "EVENT": "synchronize"}, "none"),
        ("synchronize+broken -> disable_and_triage", {"VERDICT": "automerge", "FILES_OK": "false", "EVENT": "synchronize"}, "disable_and_triage"),
        ("opened+broken -> disable_and_triage", {"VERDICT": "automerge", "FILES_OK": "false", "EVENT": "opened"}, "disable_and_triage"),
        ("outside allowlist -> triage", {"VERDICT": "triage", "FILES_OK": "", "EVENT": "opened"}, "triage"),
    ]
    for label, envs, expected in cases:
        r = run_step(steps["decide"], {}, envs)
        check(label, r["rc"] == 0 and r["outputs"].get("action") == expected, f"rc={r['rc']} err={r['stderr'][:200]}")


def test_enable(steps: dict[str, str]) -> None:
    print("enable:")
    enable_key = next(k for k in steps if k.startswith("Enable auto-merge"))
    r = run_step(steps[enable_key], {}, {})
    ok = r["rc"] == 0 and any("pr merge --auto" in c for c in r["calls"]) and any("pr comment" in c for c in r["calls"])
    check("enable: auto-merge requested + commented", ok, str(r["calls"]))
    r = run_step(steps[enable_key], {"GHSTUB_AUTO_FAILS": "1"}, {})
    check("enable: failure is not suppressed", r["rc"] != 0)


def test_keep(steps: dict[str, str]) -> None:
    print("keep:")
    keep_key = next(k for k in steps if k.startswith("Keep auto-merge"))
    r = run_step(steps[keep_key], {}, {})
    check("keep: silent no-op (no gh calls)", r["rc"] == 0 and not r["calls"])


def test_disable(steps: dict[str, str]) -> None:
    print("disable (P1 core):")
    disable_key = next(k for k in steps if k.startswith("Fail-closed - disable"))
    enabled = "enabled_by_someone\n"

    r = run_step(steps[disable_key], {"_AM_STATE": ""}, {})
    check(
        "not enabled: tolerated, label+comment posted",
        r["rc"] == 0 and not any("--disable-auto" in c for c in r["calls"]) and any("pr comment" in c for c in r["calls"]),
        f"rc={r['rc']} calls={r['calls']}",
    )

    r = run_step(steps[disable_key], {"_AM_STATE": enabled}, {})
    check(
        "enabled+disable ok: confirmed off, commented",
        r["rc"] == 0 and any("--disable-auto" in c for c in r["calls"]) and r["am_state"] == "" and any("pr comment" in c for c in r["calls"]),
        f"rc={r['rc']} am_state={r['am_state']!r}",
    )

    r = run_step(steps[disable_key], {"_AM_STATE": enabled, "GHSTUB_STATE_API_FAILS": "1"}, {})
    check(
        "state query fails: job fails, NO comment",
        r["rc"] != 0 and not any("pr comment" in c for c in r["calls"]) and "::error::" in r["stderr"],
        f"rc={r['rc']} stderr={r['stderr'][:120]}",
    )

    r = run_step(steps[disable_key], {"_AM_STATE": enabled, "GHSTUB_DISABLE_FAILS": "1"}, {})
    check(
        "disable fails: job fails, NO comment (P1 regression guard)",
        r["rc"] != 0 and not any("pr comment" in c for c in r["calls"]) and "Manual intervention" in r["stderr"],
        f"rc={r['rc']} stderr={r['stderr'][:120]}",
    )

    r = run_step(steps[disable_key], {"_AM_STATE": enabled, "GHSTUB_DISABLE_IGNORING": "1"}, {})
    check(
        "disable silently ignored by API: job fails, NO comment",
        r["rc"] != 0 and not any("pr comment" in c for c in r["calls"]) and r["am_state"] != "",
        f"rc={r['rc']} am_state={r['am_state']!r}",
    )


def main() -> int:
    if shutil.which("bash") is None:
        sys.exit("bash is required")
    trigger, steps = load_steps()
    test_structure(trigger, steps)
    test_classify(steps)
    test_guard(steps)
    test_decide(steps)
    test_enable(steps)
    test_keep(steps)
    test_disable(steps)
    print(f"\n{CHECKS - len(FAILURES)}/{CHECKS} checks passed")
    if FAILURES:
        print("FAILURES:")
        for f in FAILURES:
            print(f"  - {f}")
        return 1
    print("dependabot-automerge workflow guard: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
