#!/usr/bin/env python3
"""Registry v42b — fill merge_sha for FIXED entries credited without SHA (owner checklist lines).

For every FIXED_VERIFIED_ON_MAIN entry with a fix_pr but no merge_sha: fetch the PR's
merge state from GitHub. If merged -> merge_sha = merge_commit_sha. If NOT merged ->
the owner credit is premature: downgrade to FIX_IN_PROGRESS and report.
"""
import json
import os
import time
import urllib.request

PAT = os.environ["GH_PAT"]  # never hardcode: run with GH_PAT=<token> python3 scripts/registry_v42b_fill_sha.py
PATH = "docs/audit-registry/registry.json"


def fetch_pr(n: int):
    req = urllib.request.Request(
        f"https://api.github.com/repos/drsapaev/final/pulls/{n}",
        headers={"Authorization": f"Bearer {PAT}", "User-Agent": "c"},
    )
    try:
        with urllib.request.urlopen(req) as r:
            return json.load(r)
    except Exception as exc:  # noqa: BLE001
        return {"_error": str(exc)}


reg = json.load(open(PATH, encoding="utf-8"))
need = [e for e in reg["entries"] if e["status"] == "FIXED_VERIFIED_ON_MAIN" and e.get("fix_pr") and not e.get("merge_sha")]
print(f"FIXED entries needing merge_sha: {len(need)}")

filled, downgraded = [], []
for e in need:
    p = fetch_pr(e["fix_pr"])
    if p.get("merged"):
        e["merge_sha"] = p["merge_commit_sha"]
        filled.append((e["id"], e["fix_pr"], e["merge_sha"][:9]))
    elif "_error" in p:
        print(f"API error for {e['id']} PR #{e['fix_pr']}: {p['_error'][:80]}")
    else:
        e["status"] = "FIX_IN_PROGRESS"
        downgraded.append((e["id"], e["fix_pr"]))
    time.sleep(0.3)

json.dump(reg, open(PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print(f"filled: {len(filled)}; downgraded (PR not merged): {downgraded}")
for t, n, s in filled[:8]:
    print(f"  {t} <- #{n} {s}")
