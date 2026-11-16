#!/usr/bin/env python3
"""Registry v43 — cycle-25: REGAGG-FE-001/002 -> FIX_PROPOSED_DRAFT (gated fix PR #4107);
DERMAGALLERY-FE-007 += owner #4103 supplement evidence (28/28 GREEN on exact main d7eb97292)."""
import json

PATH = "docs/audit-registry/registry.json"

reg = json.load(open(PATH, encoding="utf-8"))
by_id = {e["id"]: e for e in reg["entries"]}

for tid in ("REGAGG-FE-001", "REGAGG-FE-002"):
    e = by_id[tid]
    assert e["status"] == "CONFIRMED_OPEN", (tid, e["status"])
    e["status"] = "FIX_PROPOSED_DRAFT"
    e["fix_pr"] = 4107
    e["test_before"] = (
        "RED before patch (registry-agent, PR head d7e572bc9 vs base d7eb97292): 6/7 new group100 "
        "acceptance tests failed — identity collision (2 unknown entries -> 1 card) and first-row "
        "status misrepresentation reproduced deterministically"
    )
    e["test_after"] = (
        "GREEN after patch: target file 44/44; full frontend suite 4338/4338; production build OK; "
        "agent gate PASS (--known-root-cause frontend/src/utils/registrarAggregation.ts, scope = 6 touched files); "
        "mixed badge + per-record breakdown (grouped_records[].status / grouped_record_statuses); "
        "same verified patient_id still aggregates into one card"
    )
    e["reviewer"] = "registry-agent gated wave 2026-11-16 (owner group100 fail-first acceptance)"
    e["date"] = "2026-11-16"

gal = by_id["DERMAGALLERY-FE-007"]
gal["test_after"] = (gal.get("test_after") or "") + (
    " | 2026-11-16 registry-agent recheck on exact main d7eb97292: owner supplement #4103 "
    "(replenishing preview worker pool — stalled private preview no longer starves later photos) "
    "merged; DermaVisitGallery.test.tsx 28/28 GREEN"
)
gal["date"] = "2026-11-16"

json.dump(reg, open(PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

statuses = {}
for x in reg["entries"]:
    statuses[x["status"]] = statuses.get(x["status"], 0) + 1
print(f"total={len(reg['entries'])}; {statuses}")
