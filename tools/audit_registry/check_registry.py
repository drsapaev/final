#!/usr/bin/env python3
"""Audit remediation registry checker (issue #4063).

Modes:
  (default)           Validate docs/audit-registry/registry.json schema + evidence rules.
  --issue-check       Additionally fetch GitHub issue #4063 live and cross-check
                      that every checklist ID exists in the registry and vice versa
                      (no finding may be lost or renamed silently).
  --final-closure     Additionally fail while any entry is UNVERIFIED / CONFIRMED_OPEN /
                      FIX_IN_PROGRESS / FIX_PROPOSED_DRAFT (for the final audit-closure
                      gate; intermediate fix PRs must NOT be blocked by this).

Exit codes: 0 = ok, 1 = violation (message printed).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REGISTRY_PATH = Path(__file__).resolve().parents[2] / "docs" / "audit-registry" / "registry.json"

VALID_STATUSES = {
    "UNVERIFIED",
    "CONFIRMED_OPEN",
    "FIX_IN_PROGRESS",
    "FIX_PROPOSED_DRAFT",
    "FIXED_VERIFIED_ON_MAIN",
    "DUPLICATE",
    "REFUTED",
    "OWNER_ACCEPTED_RISK",
}
CLOSED_STATUSES = {"FIXED_VERIFIED_ON_MAIN", "DUPLICATE", "REFUTED", "OWNER_ACCEPTED_RISK"}
OPEN_STATUSES = {"UNVERIFIED", "CONFIRMED_OPEN", "FIX_IN_PROGRESS", "FIX_PROPOSED_DRAFT"}

ID_RE = re.compile(r"`([A-Z0-9][A-Z0-9_-]*-(?:BE|FE)-\d{3})`")


def fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    sys.exit(1)


def load_registry() -> dict:
    if not REGISTRY_PATH.exists():
        fail(f"registry not found: {REGISTRY_PATH}")
    try:
        return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        fail(f"registry is not valid JSON: {e}")


def validate_schema(reg: dict) -> list[dict]:
    entries = reg.get("entries")
    if not isinstance(entries, list) or not entries:
        fail("registry has no entries")
    seen: dict[str, dict] = {}
    for e in entries:
        fid = e.get("id")
        if not fid or not isinstance(fid, str):
            fail(f"entry without id: {e!r}")
        if fid in seen:
            fail(f"duplicate registry id: {fid} (a finding must never be closed twice under different names)")
        seen[fid] = e
        status = e.get("status")
        if status not in VALID_STATUSES:
            fail(f"{fid}: invalid status {status!r}")
        if status == "FIXED_VERIFIED_ON_MAIN":
            for field in ("fix_pr", "merge_sha", "test_before", "test_after", "reviewer", "date"):
                if not e.get(field):
                    fail(f"{fid}: FIXED_VERIFIED_ON_MAIN requires non-empty '{field}' "
                         f"(merged fix PR + current-main evidence is mandatory)")
        if status in ("DUPLICATE",) and not e.get("alias_of"):
            fail(f"{fid}: DUPLICATE requires 'alias_of' (canonical ID)")
        if status in ("REFUTED", "OWNER_ACCEPTED_RISK") and not e.get("justification"):
            fail(f"{fid}: {status} requires a 'justification' with concrete evidence "
                 f"(test or source), accepted-risk also requires owner sign-off")
        if status == "CONFIRMED_OPEN" and not e.get("root_cause"):
            fail(f"{fid}: CONFIRMED_OPEN requires a confirmed 'root_cause'")
    return entries


def crosscheck_issue(entries: list[dict], pat: str | None) -> None:
    import urllib.request

    issue_id = 4063
    url = f"https://api.github.com/repos/drsapaev/final/issues/{issue_id}"
    req = urllib.request.Request(url, headers={"User-Agent": "audit-registry-checker",
                                               **({"Authorization": f"Bearer {pat}"} if pat else {})})
    try:
        body = json.load(urllib.request.urlopen(req)).get("body") or ""
    except Exception as e:  # noqa: BLE001
        fail(f"could not fetch issue #{issue_id}: {e}")
    issue_ids = set(ID_RE.findall(body))
    reg_ids = {e["id"] for e in entries}
    missing_in_registry = sorted(issue_ids - reg_ids)
    missing_in_issue = sorted(reg_ids - issue_ids)
    if missing_in_registry:
        fail(f"IDs present in issue #{issue_id} but missing from registry (new findings must be "
             f"added automatically, never dropped): {missing_in_registry}")
    if missing_in_issue:
        fail(f"IDs present in registry but no longer in issue #{issue_id} checklist "
             f"(checklist items must not be silently deleted): {missing_in_issue}")


def final_closure(entries: list[dict]) -> None:
    open_entries = [e["id"] for e in entries if e["status"] in OPEN_STATUSES]
    if open_entries:
        from collections import Counter
        c = Counter(next(e["status"] for e in entries if e["id"] == fid) for fid in open_entries)
        fail("final audit closure blocked — open statuses remain: "
             + ", ".join(f"{k}={v}" for k, v in c.items())
             + f"; first 20: {open_entries[:20]}")
    print("final closure check passed: every finding is FIXED_VERIFIED_ON_MAIN / DUPLICATE / REFUTED / OWNER_ACCEPTED_RISK")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--issue-check", action="store_true")
    ap.add_argument("--final-closure", action="store_true")
    ap.add_argument("--issue-token", default=None, help="GitHub token for higher rate limits")
    args = ap.parse_args()

    reg = load_registry()
    entries = validate_schema(reg)

    from collections import Counter
    print("status counts:", dict(Counter(e["status"] for e in entries)))
    print(f"total: {len(entries)}")

    if args.issue_check:
        crosscheck_issue(entries, args.issue_token)
        print("issue cross-check passed: registry and #4063 checklist are 1:1")

    if args.final_closure:
        final_closure(entries)

    print("OK")


if __name__ == "__main__":
    main()
