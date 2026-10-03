#!/usr/bin/env python3
"""Repeatable tests for .github/workflows/uptime-monitor.yml.

Locks the incident-management logic (issue #3562 follow-up):

  1. Structural assertions on the workflow YAML (triggers, step wiring,
     the no-data guard on the backup branch - an EMPTY backupStatus must
     not open/update the backup-stale incident).
  2. Behavioral tests that extract the REAL github-script step from the
     YAML, substitute the probe outputs the way GitHub Actions would,
     and execute it under node with a stubbed github/core/context that
     records every API call - so a future edit that reintroduces the
     "no data - still an incident" false positive fails here.

Observed defect being locked out (#3562): during a pure tunnel outage
(HTTP 530 / error 1033) the probe step exits before the backup-freshness
section, leaving backup_status/backup_age UNSET; the old guard
`backupStatus !== 'ok'` then opened/updated the backup incident with
fabricated values ("newest backup is h old", "status: ").

Run: python scripts/check_uptime_monitor_workflow.py
CI:  .github/workflows/uptime-guard-tests.yml (paths-filtered).
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.exit("PyYAML is required: pip install pyyaml")

REPO = Path(__file__).resolve().parents[1]
WORKFLOW = REPO / ".github" / "workflows" / "uptime-monitor.yml"

FAILURES: list[str] = []
CHECKS = 0

PLACEHOLDERS = (
    "${{ steps.probe.outputs.result }}",
    "${{ steps.probe.outputs.status }}",
    "${{ steps.probe.outputs.body }}",
    "${{ steps.probe.outputs.backup_status }}",
    "${{ steps.probe.outputs.backup_age }}",
)


def check(name: str, cond: bool, detail: str = "") -> None:
    global CHECKS
    CHECKS += 1
    if cond:
        print(f"  ok  {name}")
    else:
        FAILURES.append(f"{name}" + (f" :: {detail}" if detail else ""))
        print(f" FAIL {name}" + (f" :: {detail}" if detail else ""))


def load_workflow() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def get_steps(data: dict) -> list[dict]:
    return data["jobs"]["probe"]["steps"]


def step_run(steps: list[dict], name_prefix: str) -> str:
    for s in steps:
        if (s.get("name") or "").startswith(name_prefix):
            return (s.get("run") or "").replace("\r\n", "\n").replace("\r", "\n")
    raise AssertionError(f"step {name_prefix!r} not found")


def step_with_script(steps: list[dict], name_prefix: str) -> str:
    for s in steps:
        if (s.get("name") or "").startswith(name_prefix):
            script = (s.get("with") or {}).get("script") or ""
            return script.replace("\r\n", "\n").replace("\r", "\n")
    raise AssertionError(f"step {name_prefix!r} not found")


# --- structural assertions ----------------------------------------------------


def structural_checks() -> tuple[str, str]:
    data = load_workflow()
    trigger = data[True] if True in data else data["on"]
    steps = get_steps(data)
    probe_run = step_run(steps, "Probe public")
    incident_script = step_with_script(steps, "Manage incident issue")

    check("trigger: schedule */15 + workflow_dispatch",
          trigger.get("schedule") == [{"cron": "*/15 * * * *"}]
          and "workflow_dispatch" in trigger)

    manage_step = next(s for s in steps if (s.get("name") or "").startswith("Manage incident issue"))
    check("incident step runs if: always()", manage_step.get("if") == "always()")

    check("probe step: backup outputs written AFTER the health gate",
          # both early exits precede the first backup output write
          probe_run.find("result=failure") < probe_run.find("backup_status=")
          and probe_run.count("exit 1") >= 2
          and probe_run.rfind("exit 1") < probe_run.find("backup_status="))

    check("no-data guard present: backup branch requires non-empty backupStatus",
          re.search(r"if\s*\(\s*backupStatus\s*&&\s*backupStatus\s*!==\s*'ok'\s*\)", incident_script) is not None,
          "expected `if (backupStatus && backupStatus !== 'ok'))`")

    check("old unguarded branch is absent",
          re.search(r"if\s*\(\s*backupStatus\s*!==\s*'ok'\s*\)", incident_script) is None)

    check("recovery branch still gated on measured 'ok'",
          re.search(r"if\s*\(\s*backupStatus\s*===\s*'ok'\s*&&\s*backupIncident\s*\)", incident_script) is not None)

    check("uptime branch still gated on consecutive failures",
          "consecutive >= threshold" in incident_script)

    return probe_run, incident_script


# --- behavioral harness -------------------------------------------------------

HARNESS_HEAD = r"""
const calls = [];
const rec = (op, args) => calls.push({ op, args });

// Scenario data injected by the Python driver as JSON on stdin-free env:
const SCENARIO = JSON.parse(process.env.GUARD_SCENARIO);

// Stateful github stub: paginate() delegates to the recorded rest methods
// exactly like the real kit (each returns the scenario page), mutations are
// recorded and return a plausible shape.
const restPage = (name, page) => {
  const fn = async (args) => page;
  fn.__endpoint = name;
  return fn;
};
const listWorkflowRuns = restPage('actions.listWorkflowRuns', SCENARIO.runs);
const listForRepoUptime = restPage('issues.listForRepo.uptime', SCENARIO.open_uptime_issues);
const listForRepoBackup = restPage('issues.listForRepo.backup', SCENARIO.open_backup_issues);
const listForRepoOther = restPage('issues.listForRepo.other', []);

const issuesMutations = {
  createComment: async (args) => { rec('issues.createComment', args); return { data: {} }; },
  create: async (args) => { rec('issues.create', args); return { data: { number: 4242 } }; },
  update: async (args) => { rec('issues.update', args); return { data: {} }; },
};

const github = {
  paginate: async (fn, args) => {
    const page = await fn(args);
    rec('paginate:' + (fn.__endpoint || 'unknown'), args);
    return page;
  },
  rest: {
    actions: { listWorkflowRuns },
    issues: {
      listForRepo: async (args) => {
        // Distinguish by labels filter, like the real endpoint does.
        rec('issues.listForRepo', args);
        const labels = (args && args.labels) || '';
        if (labels === 'uptime-incident') return listForRepoUptime();
        if (labels === 'backup-stale') return listForRepoBackup();
        return listForRepoOther();
      },
      ...issuesMutations,
    },
  },
};
const core = {
  info: (m) => rec('core.info', { message: m }),
  debug: () => {},
  warning: (m) => rec('core.warning', { message: m }),
};
const context = { repo: { owner: 'drsapaev', repo: 'final' }, runId: 37085186879 };

(async () => {
"""

HARNESS_TAIL = r"""
})().then(() => {
  console.log('@@CALLS@@' + JSON.stringify(calls));
}).catch((e) => {
  console.error('SCRIPT_ERROR: ' + (e && e.stack || e));
  process.exit(1);
});
"""


def substitute(script: str, values: dict[str, str]) -> str:
    """Replace the `${{ steps.probe.outputs.* }}` placeholders exactly like
    GitHub Actions renders them into the script text."""
    mapping = {
        PLACEHOLDERS[0]: values["result"],
        PLACEHOLDERS[1]: values["status"],
        PLACEHOLDERS[2]: values["body"],
        PLACEHOLDERS[3]: values["backup_status"],
        PLACEHOLDERS[4]: values["backup_age"],
    }
    out = script
    for ph, val in mapping.items():
        out = out.replace(ph, val)
    leftover = re.findall(r"\$\{\{\s*steps\.probe\.outputs\.\w+\s*\}\}", out)
    if leftover:
        raise AssertionError(f"unsubstituted placeholders: {leftover}")
    return out


def run_scenario(script: str, scenario: dict) -> list[dict]:
    """Execute the real incident-management script under node with stubs."""
    node = shutil.which("node")
    if not node:
        sys.exit("node is required to run the behavioral harness")

    root = Path(tempfile.mkdtemp(prefix="uptime_guard_"))
    try:
        js = HARNESS_HEAD + substitute(script, {
            "result": scenario["result"],
            "status": scenario["status"],
            "body": scenario["body"],
            "backup_status": scenario["backup_status"],
            "backup_age": scenario["backup_age"],
        }) + HARNESS_TAIL
        js_file = root / "scenario.mjs"
        js_file.write_text(js, encoding="utf-8")

        import os
        env = dict(os.environ)
        env["GUARD_SCENARIO"] = json.dumps(scenario)
        env["CONSECUTIVE_FAILURES"] = "2"
        env["INCIDENT_LABEL"] = "uptime-incident"
        env["UPTIME_UA"] = "finalclinic-uptime/1.0"

        r = subprocess.run(
            [node, js_file.as_posix()],
            capture_output=True, text=True, env=env, timeout=60,
        )
        if r.returncode != 0:
            raise AssertionError(f"node failed: {r.stderr[-2000:]}")
        for line in r.stdout.splitlines():
            if line.startswith("@@CALLS@@"):
                return json.loads(line[len("@@CALLS@@"):])
        raise AssertionError(f"no @@CALLS@@ marker in output: {r.stdout[-2000:]} {r.stderr[-500:]}")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def ops(calls: list[dict]) -> list[str]:
    """Operation names, with issue target resolution for readability."""
    out = []
    for c in calls:
        op = c["op"]
        if op.startswith("paginate:") or op == "issues.listForRepo":
            continue  # reads are not assertions' subject
        out.append(op)
    return out


def find_call(calls: list[dict], op: str) -> dict | None:
    for c in calls:
        if c["op"] == op:
            return c["args"]
    return None


def behavioral_checks(script: str) -> None:
    run_ok = {"status": "completed", "conclusion": "success"}
    run_fail = {"status": "completed", "conclusion": "failure"}
    uptime_incident = {"number": 3563, "title": "[uptime] api.finalclinic.fyi health degraded (x)", "state": "open"}
    backup_incident = {"number": 3562, "title": "[backup] production backup stale (>26h) (x)", "state": "open"}

    # A. THE BUG (observed in #3562): probe fails on tunnel error -> backup
    # outputs unset. The backup incident must NOT be created or updated.
    calls = run_scenario(script, {
        "result": "failure", "status": "530", "body": "error code: 1033",
        "backup_status": "", "backup_age": "",
        "runs": [run_fail], "open_uptime_issues": [], "open_backup_issues": [],
    })
    check("A: tunnel outage opens the uptime incident (2nd consecutive failure)",
          find_call(calls, "issues.create") is not None
          and "[uptime]" in (find_call(calls, "issues.create") or {}).get("title", ""))
    check("A: tunnel outage does NOT create a backup incident",
          not any("[backup]" in ((c.get("args") or {}).get("title") or "")
                  for c in calls if c["op"] == "issues.create"))
    check("A: no comments anywhere with fabricated empty backup values",
          not any("is  h old" in ((c.get("args") or {}).get("body") or "")
                  for c in calls if c["op"] == "issues.createComment"))

    # B. Probe fails while a REAL backup incident is already open: no-data
    # must not spam it with empty-value comments (but uptime still updates).
    calls = run_scenario(script, {
        "result": "failure", "status": "530", "body": "error code: 1033",
        "backup_status": "", "backup_age": "",
        "runs": [run_fail, run_fail], "open_uptime_issues": [uptime_incident],
        "open_backup_issues": [backup_incident],
    })
    check("B: uptime incident gets a 'Still down.' comment",
          any(c["op"] == "issues.createComment" and c["args"].get("issue_number") == 3563
              and "Still down." in c["args"].get("body", "") for c in calls))
    check("B: existing backup incident is NOT touched without data",
          not any(c["op"] == "issues.createComment" and c["args"].get("issue_number") == 3562 for c in calls)
          and not any(c["op"] == "issues.update" and c["args"].get("issue_number") == 3562 for c in calls))

    # C. Probe ok, backup measured stale -> incident created with the real age.
    calls = run_scenario(script, {
        "result": "success", "status": "200", "body": '{"ok":true,"db":"ok"}',
        "backup_status": "stale", "backup_age": "27.5",
        "runs": [run_ok], "open_uptime_issues": [], "open_backup_issues": [],
    })
    created = find_call(calls, "issues.create")
    check("C: measured 'stale' creates the backup incident",
          created is not None and "[backup]" in (created or {}).get("title", ""))
    check("C: backup incident body carries the measured age",
          created is not None and "27.5h old" in (created or {}).get("body", ""))

    # D. Probe ok, backup ok, incident open -> recovery comment + close.
    calls = run_scenario(script, {
        "result": "success", "status": "200", "body": '{"ok":true,"db":"ok"}',
        "backup_status": "ok", "backup_age": "2.1",
        "runs": [run_ok], "open_uptime_issues": [], "open_backup_issues": [backup_incident],
    })
    check("D: recovery comment on the backup incident",
          any(c["op"] == "issues.createComment" and c["args"].get("issue_number") == 3562
              and "Recovered" in c["args"].get("body", "") for c in calls))
    check("D: backup incident closed",
          any(c["op"] == "issues.update" and c["args"].get("issue_number") == 3562
              and c["args"].get("state") == "closed" for c in calls))

    # E. Probe ok, /health/detailed unusable -> 'unknown' is a MEASURED value
    # and still alerts (regression guard for over-broad no-data skips).
    calls = run_scenario(script, {
        "result": "success", "status": "200", "body": '{"ok":true,"db":"ok"}',
        "backup_status": "unknown", "backup_age": "?",
        "runs": [run_ok], "open_uptime_issues": [], "open_backup_issues": [],
    })
    created = find_call(calls, "issues.create")
    check("E: measured 'unknown' still creates the backup incident",
          created is not None and "[backup]" in (created or {}).get("title", ""))

    # F. First failure below the consecutive threshold -> no uptime incident.
    calls = run_scenario(script, {
        "result": "failure", "status": "530", "body": "error code: 1033",
        "backup_status": "", "backup_age": "",
        "runs": [run_ok], "open_uptime_issues": [], "open_backup_issues": [],
    })
    check("F: single failure below threshold opens nothing",
          find_call(calls, "issues.create") is None
          and find_call(calls, "issues.createComment") is None)

    # G. Probe ok while uptime incident open -> uptime recovery + close.
    calls = run_scenario(script, {
        "result": "success", "status": "200", "body": '{"ok":true,"db":"ok"}',
        "backup_status": "ok", "backup_age": "2.1",
        "runs": [run_ok], "open_uptime_issues": [uptime_incident], "open_backup_issues": [],
    })
    check("G: uptime incident recovered and closed",
          any(c["op"] == "issues.update" and c["args"].get("issue_number") == 3563
              and c["args"].get("state") == "closed" for c in calls))


def main() -> int:
    print(f"workflow guard checks: {WORKFLOW}")
    _probe_run, incident_script = structural_checks()
    print("behavioral scenarios (real github-script step under node):")
    behavioral_checks(incident_script)
    print()
    if FAILURES:
        print(f"FAILED: {len(FAILURES)} of {CHECKS} checks")
        for f in FAILURES:
            print(f"  - {f}")
        return 1
    print(f"OK: all {CHECKS} checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
