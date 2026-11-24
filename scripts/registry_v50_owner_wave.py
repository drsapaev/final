#!/usr/bin/env python3
"""Registry v50 — cycle-31 (2026-11-24): owner merge wave verification on
origin/main be42ec561. Three registry claims repaired by dedicated owner PRs,
each with a dedicated regression suite executed green on the exact merged tree
(12/12 across 3 suites, node_modules rebuilt)."""
import json

PATH = "docs/audit-registry/registry.json"

UPGRADES = [
    ("DERMSCHED-FE-003", "#4248", "b40a15a4d",
     "CONFIRMED on current main 2026-11-15: loadPatients() issues api.get('/patients') with NO q/skip/limit/selected-patient option and renders only the returned array — the canonical endpoint defaults to a small first page, so the patient picker cannot reach patients beyond it",
     "owner PR #4248 (merge b40a15a4d, 'patient picker reaches beyond the first default page'): ScheduleNextModal patient search now passes q/skip/limit (+selected-patient handling, 30 pattern hits in diff); dedicated suite ScheduleNextModal.patientSearch.test.tsx (155 lines) GREEN — 3 suites 12/12 total on merged tree; registry-agent verification 2026-11-24"),
    ("DERMSCHED-FE-004", "#4243", "08a4654e1",
     "CONFIRMED on current main 2026-11-15: the post-success dismiss timer is a bare untracked setTimeout(()=>{onClose?.();resetForm();},2000) (ScheduleNextModal.tsx:241) — no clearTimeout on unmount or modal reopen, so a stale timer dismisses a freshly reopened dialog",
     "owner PR #4243 (merge 08a4654e1, 'stale success timer can no longer dismiss a reopened schedule-next dialog'): tracked timer with cleanup (clearTimeout/timerRef patterns in diff); dedicated suite ScheduleNextModal.timer.test.tsx (120 lines) GREEN — 3 suites 12/12 total on merged tree; registry-agent verification 2026-11-24"),
    ("DERMATIMELINE-FE-001", "#4245", "c5f87d92a",
     "UNVERIFIED: claim evidence https://github.com/drsapaev/final/pull/3892#issuecomment-6690449597 (VisitTimeline reporting an in-progress EMR draft as completed)",
     "owner PR #4245 (merge c5f87d92a, 'a true EMR draft is no longer reported as completed'): VisitTimeline draft-state discrimination added (23 draft/completed pattern hits in diff); dedicated suite VisitTimeline.draftState.test.tsx (93 lines) GREEN — 3 suites 12/12 total on merged tree; registry-agent verification 2026-11-24"),
]

reg = json.load(open(PATH, encoding="utf-8"))
touched = []
for e in reg["entries"]:
    for uid, pr, sha, before, after in UPGRADES:
        if e["id"] != uid:
            continue
        e["status"] = "FIXED_VERIFIED_ON_MAIN"
        e["checked"] = True
        e["fix_pr"] = pr
        e["merge_sha"] = sha
        e["test_before"] = before
        e["test_after"] = after
        e["reviewer"] = "registry-agent cycle-31: commit diff read + dedicated owner suites executed green on exact merged tree be42ec561"
        e["date"] = "2026-11-24"
        touched.append(uid)

json.dump(reg, open(PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
statuses = {}
for x in reg["entries"]:
    statuses[x["status"]] = statuses.get(x["status"], 0) + 1
print(f"touched: {touched}")
print(f"total={len(reg['entries'])}; {statuses}")
