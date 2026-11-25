#!/usr/bin/env python3
"""Registry v46 addendum — the last 7 Group107 IDs (post-merge review fixes
#3915/#3917) + corrected evidence for EMRRESTORE-FE-002."""
import json

PATH = "docs/audit-registry/registry.json"

FIXES = {
    "DOCFLOW-FE-004": ("3915", "b13f570c9", "frontend/src/pages/CardiologistPanelUnified.tsx + DoctorVisitCompletionAck.contract.test.ts"),
    "DOCQ-FE-004": ("3915", "b13f570c9", "frontend/src/components/doctor/DoctorQueuePanel.tsx + DoctorQueuePanel.canonicalClient.test.tsx"),
    "LABAI-FE-003": ("3915", "b13f570c9", "frontend/src/components/ai/AIAssistant.tsx + AIAssistant.loadingOwnership.contract.test.ts"),
    "LABQ-FE-004": ("3915", "b13f570c9", "frontend/src/pages/LabPanel.tsx + LabPanel.queueGeneration.test.tsx"),
    "LABR-FE-003": ("3915", "b13f570c9", "frontend/src/components/laboratory/LabReportWorkbench.tsx + LabReportPreview.staleContext.test.tsx"),
    "LABEDIT-FE-003": ("3917", "8bb3762c2", "frontend/src/components/laboratory/ReportEditor.tsx + ReportEditor.trendAndFlagFreshness.test.tsx"),
    "LABEDIT-FE-004": ("3917", "8bb3762c2", "frontend/src/components/laboratory/ReportEditor.tsx + ReportEditor.trendPredecessorIdentity.test.tsx"),
}

REVIEWER = ("registry-agent Group107 triage 2026-11-23: fix commit subject enumerates ID + "
            "ID confirmed in origin/main tree (f4993c503) with dedicated regression test")

reg = json.load(open(PATH, encoding="utf-8"))
touched = []
for e in reg["entries"]:
    if e["id"] == "EMRRESTORE-FE-002":
        e["test_after"] = (
            "owner audit-3886 round 16 repair PR #3923 (merge 372d6924e) enumerates EMRRESTORE-FE-002 "
            "in its subject; in-tree evidence: backend/app/services/emr_v2_service.py (restore rejected "
            "for finalized records with explicit reason) + backend/tests/unit/test_emr_v2_lifecycle_guards.py "
            "(504 lines); registry-agent triage 2026-11-23 on origin/main f4993c503"
        )
        touched.append("EMRRESTORE-FE-002 (evidence corrected)")
        continue
    f = FIXES.get(e["id"])
    if f is None or e["status"] != "UNVERIFIED":
        continue
    pr, sha, ev = f
    e["status"] = "FIXED_VERIFIED_ON_MAIN"
    e["checked"] = True
    e["fix_pr"] = f"#{pr}"
    e["merge_sha"] = sha
    e["test_before"] = "owner audit-3886 ledger #3886 claim (historical, docs-only source review, no runtime repro at claim time)"
    e["test_after"] = (
        f"owner post-merge review repair PR #{pr} (merge {sha}) enumerates {e['id']} in its subject; "
        f"in-tree evidence: {ev}; registry-agent triage 2026-11-23 on origin/main f4993c503"
    )
    e["reviewer"] = REVIEWER
    e["date"] = "2026-11-23"
    touched.append(e["id"])

json.dump(reg, open(PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
statuses = {}
for x in reg["entries"]:
    statuses[x["status"]] = statuses.get(x["status"], 0) + 1
g107_unv = [e["id"] for e in reg["entries"] if e["status"] == "UNVERIFIED" and str(e.get("source", "")).startswith("#4063 Group107")]
print(f"touched: {touched}")
print(f"Group107 still UNVERIFIED: {g107_unv}")
print(f"total={len(reg['entries'])}; {statuses}")
