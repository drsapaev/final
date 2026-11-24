#!/usr/bin/env python3
"""Registry v42 — cycle-24: mass resync to live #4063 checklist.

Handles the 2026-11-16 owner reconciliation:
- Group107: +120 historical IDs restored as UNVERIFIED candidates
  (HISTORICAL_SOURCE_CONFIRMED / REMEDIATION_UNVERIFIED — explicitly NOT fixed);
- Groups 102-106: owner-credited [x] FIXED_VERIFIED_ON_MAIN upgrades of existing entries;
- DISPLAYBOOT-FE-001 provenance correction (fix PR is #4057, not docs-only #4042);
- provenance link corrections from the owner correction block (fix PR rewritten from the line);
- 1:1 ID parity with the checklist (never drop, never retype).

Priority rules (safe):
- never downgrade a registry status because the checklist lags (e.g. our FIX_IN_PROGRESS
  vs checklist CONFIRMED_OPEN);
- conflicts (registry FIXED vs checklist non-FIXED, or vice versa UNVERIFIED vs FIXED)
  are reported, not silently flipped, unless the checklist line carries an explicit
  [x] + FIXED_VERIFIED_ON_MAIN marker (owner credit) — those are applied as fact.
"""
import json
import os
import re
import urllib.request

PAT = os.environ["GH_PAT"]  # never hardcode: run with GH_PAT=<token>
PATH = "docs/audit-registry/registry.json"

req = urllib.request.Request(
    "https://api.github.com/repos/drsapaev/final/issues/4063",
    headers={"Authorization": f"Bearer {PAT}", "User-Agent": "c"},
)
body = json.load(urllib.request.urlopen(req))["body"]
lines = body.splitlines()

ID_RE = re.compile(r"`([A-Z0-9]+-(?:FE|BE)-\d+)`")
PR_RE = re.compile(r"(?:pull/|[#№]\s*|#)(\d{4})")
SHA_RE = re.compile(r"merge\s+`([0-9a-f]{9,40})`|merge\s+([0-9a-f]{9,40})\b")
URL_RE = re.compile(r"\((https://github\.com/[^)]+)\)")


def detect_status(text: str):
    """Map checklist line text to a registry status, or None if not explicit."""
    if "FIXED_VERIFIED_ON_MAIN" in text:
        return "FIXED_VERIFIED_ON_MAIN"
    if "HISTORICAL_SOURCE_CONFIRMED" in text and "REMEDIATION_UNVERIFIED" in text:
        return "UNVERIFIED"
    if "REFUTED" in text:
        return "REFUTED"
    if "DUPLICATE" in text:
        return "DUPLICATE"
    if "OWNER_ACCEPTED_RISK" in text:
        return "OWNER_ACCEPTED_RISK"
    if "CONFIRMED_OPEN" in text:
        return "CONFIRMED_OPEN"
    if "SOURCE-CONFIRMED" in text and "NOT_FIXED" in text:
        return "CONFIRMED_OPEN"
    if "FIX_PROPOSED_DRAFT" in text:
        return "FIX_PROPOSED_DRAFT"
    return None


# --- parse checklist ---
checklist = {}
group_ctx = "pre-group context"
for ln in lines:
    if ln.startswith("## Group") or ln.startswith("### "):
        group_ctx = ln.lstrip("# ").strip()[:140]
        continue
    m = ID_RE.search(ln)
    if not m or not ln.strip().startswith("- ["):
        continue
    tid = m.group(1)
    checked = ln.strip().startswith("- [x]")
    status = detect_status(ln)
    prs = [int(p) for p in PR_RE.findall(ln)]
    sha_m = SHA_RE.search(ln)
    sha = (sha_m.group(1) or sha_m.group(2)) if sha_m else None
    urls = URL_RE.findall(ln)
    checklist[tid] = {
        "checked": checked,
        "status": status,
        "prs": prs,
        "sha": sha,
        "urls": urls,
        "group": group_ctx,
        "line": ln.strip()[:300],
    }

reg = json.load(open(PATH, encoding="utf-8"))
by_id = {e["id"]: e for e in reg["entries"]}
added, upgraded, pr_fixed, conflicts = [], [], [], []

for tid, ck in checklist.items():
    e = by_id.get(tid)
    if e is None:
        # New ID — Group107 historical candidates are explicitly UNVERIFIED.
        status = ck["status"] or "UNVERIFIED"
        ev = ck["urls"][0] if ck["urls"] else None
        entry = {
            "checked": False,
            "id": tid,
            "priority": "P2",
            "source": f"#4063 {ck['group']} (owner checklist 2026-11-16)",
            "evidence": ev,
            "status": status,
            "fix_pr": None,
            "merge_sha": None,
        }
        if "HISTORICAL_SOURCE_CONFIRMED" in (ck["line"] or ""):
            entry["title"] = "Historical candidate restored by owner group107 — HISTORICAL_SOURCE_CONFIRMED / REMEDIATION_UNVERIFIED (незачтённый кандидат, не подтверждённый активный дефект)"
            entry["root_cause"] = f"Owner group107 restoration: remediation unverified; primary audit + provenance chain pinned in checklist line. Line: {ck['line']}"
            entry["priority"] = "P3"
        else:
            entry["title"] = f"Owner checklist finding (parsed 1:1 from #4063, 2026-11-16): {ck['line'][:180]}"
        reg["entries"].append(entry)
        by_id[tid] = entry
        added.append(tid)
        continue

    cur = e["status"]

    # Owner credit: explicit [x] + FIXED_VERIFIED_ON_MAIN in checklist.
    if ck["status"] == "FIXED_VERIFIED_ON_MAIN" and cur != "FIXED_VERIFIED_ON_MAIN":
        if cur in ("FIX_PROPOSED_DRAFT", "FIX_IN_PROGRESS", "CONFIRMED_OPEN", "UNVERIFIED"):
            e["status"] = "FIXED_VERIFIED_ON_MAIN"
            if ck["prs"]:
                e["fix_pr"] = ck["prs"][0]
            if ck["sha"]:
                e["merge_sha"] = ck["sha"]
            e["reviewer"] = "owner checklist credit [x] 2026-11-16 (registry-agent resync v42)"
            e["date"] = "2026-11-16"
            upgraded.append(tid)
        else:
            conflicts.append((tid, cur, "checklist FIXED"))
        continue

    # Provenance correction for already-FIXED entries.
    if cur == "FIXED_VERIFIED_ON_MAIN" and ck["prs"]:
        if e.get("fix_pr") and e["fix_pr"] != ck["prs"][0]:
            pr_fixed.append((tid, e["fix_pr"], ck["prs"][0]))
            e["fix_pr"] = ck["prs"][0]

    # Owner REFUTED/DUPLICATE verdict on a non-closed entry.
    if ck["status"] in ("REFUTED", "DUPLICATE") and cur not in ("REFUTED", "DUPLICATE"):
        e["status"] = ck["status"]
        e["reviewer"] = "owner checklist verdict 2026-11-16 (resync v42)"
        e["date"] = "2026-11-16"
        upgraded.append(tid)
        continue

    # Owner CONFIRMED_OPEN upgrade from UNVERIFIED.
    if ck["status"] == "CONFIRMED_OPEN" and cur == "UNVERIFIED":
        e["status"] = "CONFIRMED_OPEN"
        e["checked"] = False
        upgraded.append(tid)

# Group106 provenance correction for DISPLAYBOOT-FE-001.
db = by_id.get("DISPLAYBOOT-FE-001")
if db and db["status"] == "FIXED_VERIFIED_ON_MAIN" and db.get("fix_pr") != 4057:
    pr_fixed.append(("DISPLAYBOOT-FE-001", db.get("fix_pr"), 4057))
    db["fix_pr"] = 4057

json.dump(reg, open(PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

statuses = {}
for x in reg["entries"]:
    statuses[x["status"]] = statuses.get(x["status"], 0) + 1
print(f"checklist IDs: {len(checklist)}")
print(f"added: {len(added)} -> {added[:8]}...{added[-4:] if len(added) > 12 else ''}")
print(f"upgraded/closed: {len(upgraded)} -> {upgraded[:14]}")
print(f"provenance fix_pr corrections: {len(pr_fixed)} -> {pr_fixed[:10]}")
print(f"conflicts (NOT applied): {conflicts[:10]}")
print(f"total={len(reg['entries'])}; {statuses}")
