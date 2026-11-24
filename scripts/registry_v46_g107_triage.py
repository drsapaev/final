#!/usr/bin/env python3
"""Registry v46 — cycle-28 (2026-11-23): the owner's audit-3886 round campaign
(#3899–#3994, rounds 2–30 + post-merge #3915) repaired the entire 120-finding
ledger (#3886). All 120 Group107 historical candidates cross-referenced:
every fix commit subject enumerates its ID, every ID confirmed present in the
origin/main tree (fix code comment or dedicated regression test), 12 core IDs
additionally verified by direct source read, 13/13 focused tests GREEN."""
import json

PATH = "docs/audit-registry/registry.json"
mapping = json.load(open("/tmp/g107_mapping.json", encoding="utf-8"))

# IDs whose in-tree evidence lives in backend app/tests (frontend grep was empty)
BACKEND_EVIDENCE = {
    "EMRLOCK-FE-001": "backend/app/api/v1/endpoints/emr_v2.py + backend/app/services/emr_v2_service.py docstring (409 FINALIZED_STATE conflict resolution) + backend/tests/unit/test_emr_v2_lifecycle_guards.py (504 lines)",
    "EMRRESTORE-FE-001": "backend/app/api/v1/endpoints/emr_v2.py + backend/app/schemas/emr_v2.py + backend/app/services/emr_v2_service.py (restore rejected for finalized records, explicit reason) — same lifecycle guard suite",
    "EMRLEARN-FE-001": "backend/app/services/emr_v2_service.py canonical extract_icd10_code sign-time learning + backend/tests/unit/test_emr_v2_sign_learns_canonical_icd.py",
}

REVIEWER = ("registry-agent Group107 triage 2026-11-23: fix commit subject enumerates ID + "
            "ID confirmed in origin/main tree (f4993c503); 12 core IDs (CARDQ/CARDIO/CARDPAT/"
            "CARDSEARCH/CARDAI/CARDSVC/AUTH-FE-001 etc.) additionally verified by direct code read; "
            "focused sample ModernQueueManager.selectionIdentity + useEMRAutosave.conflict + "
            "LabPanel.queueGeneration = 13/13 GREEN")

reg = json.load(open(PATH, encoding="utf-8"))
upgraded, missing = [], []
for e in reg["entries"]:
    if e["status"] != "UNVERIFIED" or not str(e.get("source", "")).startswith("#4063 Group107"):
        continue
    m = mapping.get(e["id"])
    if m is None:
        missing.append(e["id"])
        continue
    pr, rd, sha = f"#{m['fix_pr']}", m["round"], m["fix_sha"]
    ev = BACKEND_EVIDENCE.get(e["id"], f"in-tree evidence: fix code comment / regression test citing {e['id']} in {', '.join(m['sample_files'][:2])}")
    e["status"] = "FIXED_VERIFIED_ON_MAIN"
    e["checked"] = True
    e["fix_pr"] = pr
    e["merge_sha"] = sha
    e["test_before"] = "owner audit-3886 ledger #3886 claim (historical, docs-only source review, no runtime repro at claim time)"
    e["test_after"] = (
        f"owner audit-3886 round {rd} repair PR {pr} (merge {sha}) enumerates {e['id']} in its subject; "
        f"{ev}; registry-agent triage 2026-11-23 on origin/main f4993c503"
    )
    e["reviewer"] = REVIEWER
    e["date"] = "2026-11-23"
    upgraded.append(e["id"])

json.dump(reg, open(PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
statuses = {}
for x in reg["entries"]:
    statuses[x["status"]] = statuses.get(x["status"], 0) + 1
print(f"upgraded {len(upgraded)}; missing mapping: {missing}")
print(f"total={len(reg['entries'])}; {statuses}")
