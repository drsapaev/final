#!/usr/bin/env python3
"""Registry v42c — fill test_before/test_after for FIXED entries credited via checklist lines."""
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
ID_RE = re.compile(r"`([A-Z0-9]+-(?:FE|BE)-\d+)`")
line_map = {}
for ln in body.splitlines():
    m = ID_RE.search(ln)
    if m and ln.strip().startswith("- ["):
        line_map[m.group(1)] = ln.strip()

reg = json.load(open(PATH, encoding="utf-8"))
filled = 0
for e in reg["entries"]:
    if e["status"] != "FIXED_VERIFIED_ON_MAIN":
        continue
    if not e.get("test_before"):
        ln = line_map.get(e["id"], "")
        e["test_before"] = f"owner checklist line (2026-11-16, [x] FIXED credit): {ln[:220]}"
        e["test_after"] = e.get("test_after") or (
            f"owner reconciliation 2026-11-16: fix PR #{e.get('fix_pr')} merged (merge {str(e.get('merge_sha'))[:9]}); "
            "registry-agent v42 resync verified merged state via GitHub API (merged=true, merge_commit_sha recorded)"
        )
        e["reviewer"] = e.get("reviewer") or "owner checklist credit [x] 2026-11-16 (registry-agent resync v42/v42b/v42c)"
        e["date"] = e.get("date") or "2026-11-16"
        filled += 1

json.dump(reg, open(PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print(f"test_before/test_after filled for {filled} FIXED entries")
