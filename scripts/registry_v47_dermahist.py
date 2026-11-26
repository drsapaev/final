#!/usr/bin/env python3
"""Registry v47 — cycle-29 (2026-11-23): owner PR #4231 (merge 63d06517b)
repairs DERMAHIST-FE-004 (CONFIRMED_OPEN 2026-11-15: history cards rendered
only date/skin type/diagnosis with no drilldown though the API already sends
lesions/distribution/symptoms/treatment_plan and procedure fields).
Verified: diff read (fields declared + per-card drilldown + i18n x5) and
dedicated suite DermaHistoryTab.details.test.tsx 4/4 GREEN on merged tree."""
import json

PATH = "docs/audit-registry/registry.json"
reg = json.load(open(PATH, encoding="utf-8"))
touched = []
for e in reg["entries"]:
    if e["id"] != "DERMAHIST-FE-004":
        continue
    e["status"] = "FIXED_VERIFIED_ON_MAIN"
    e["checked"] = True
    e["fix_pr"] = "#4231"
    e["merge_sha"] = "63d06517b"
    e["test_before"] = "CONFIRMED on current main 2026-11-15: DermaHistoryTab cards render only date/skin type/diagnosis (date/type/area for procedures), no detail drilldown though the history union already sends the fields"
    e["test_after"] = (
        "owner PR #4231 (merge 63d06517b) declares the API-sent fields (lesions/distribution/symptoms/"
        "treatment_plan; products_used/results/follow_up; source marker + visit identity) and renders "
        "per-card drilldown with i18n labels in 5 locales; dedicated regression suite "
        "DermaHistoryTab.details.test.tsx 4/4 GREEN on merged tree (registry branch = 63d06517b + registry docs), "
        "registry-agent verification 2026-11-23"
    )
    e["reviewer"] = "registry-agent cycle-29: commit diff read + dedicated suite executed on exact merged tree"
    e["date"] = "2026-11-23"
    touched.append(e["id"])

json.dump(reg, open(PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
statuses = {}
for x in reg["entries"]:
    statuses[x["status"]] = statuses.get(x["status"], 0) + 1
print(f"touched: {touched}")
print(f"total={len(reg['entries'])}; {statuses}")

# next frontier structure
groups = {}
for e in reg["entries"]:
    if e["status"] == "UNVERIFIED":
        s = str(e.get("source", ""))[:70]
        groups.setdefault(s, []).append(e["id"])
for s, ids in sorted(groups.items(), key=lambda kv: -len(kv[1]))[:6]:
    print(f"\n{len(ids):3d}  {s}")
    print("     ", " ".join(ids[:8]), "...")
