#!/usr/bin/env python3
"""Registry v44 — cycle-26: owner merges #4105/#4109/#4114 verified on exact main
835eb01b6 -> FIXED_VERIFIED_ON_MAIN (DERMAAI-FE-002, DERMACOMPLETE-FE-001, QUEUEPRINT-FE-003)."""
import json

PATH = "docs/audit-registry/registry.json"

UPGRADES = {
    "DERMAAI-FE-002": {
        "fix_pr": 4105,
        "merge_sha": "1532acda4adc0d5109e941b0681fb8091c6dd5b5",
        "evidence": (
            "owner merge #4105 (1532acda4: DermaVisitGallery fail-closed on invalid skin AI "
            "response envelope, +51 test lines); registry-agent batch verification on exact "
            "main 835eb01b6: DermaVisitGallery.test.tsx within 6-file owner-merge batch "
            "44/44 GREEN (2026-11-16)"
        ),
    },
    "DERMACOMPLETE-FE-001": {
        "fix_pr": 4109,
        "merge_sha": "eb8fff18d01729da3f719c9219148c646d41d7c0",
        "evidence": (
            "owner merge #4109 (eb8fff18d: completion honours the shared EMR dirty registry; "
            "new DermatologistPanel.dermaCompleteDirtyGate.test.tsx 347 lines + deferredAcks/"
            "races/DoctorVisitCompletionAck contract updates); registry-agent batch "
            "verification on exact main 835eb01b6: 44/44 GREEN across the 6 owner-merge "
            "test files (2026-11-16)"
        ),
    },
    "QUEUEPRINT-FE-003": {
        "fix_pr": 4114,
        "merge_sha": "835eb01b6a664ef3485a6ce4e1590313ca937b75",
        "evidence": (
            "owner merge #4114 (835eb01b6: never fabricate ticket identity from unrelated "
            "record PKs; new panelPrint.queueIdentity.test.ts 106 lines); registry-agent "
            "batch verification on exact main 835eb01b6: 44/44 GREEN across the 6 owner-merge "
            "test files (2026-11-16). Note: agent PR #4095 also proposed a FE-003 fix — the "
            "owner merge supersedes its FE-003 half; #4095 remains relevant for FE-004 only"
        ),
    },
}

reg = json.load(open(PATH, encoding="utf-8"))
by_id = {e["id"]: e for e in reg["entries"]}

for tid, up in UPGRADES.items():
    e = by_id[tid]
    e["status"] = "FIXED_VERIFIED_ON_MAIN"
    e["fix_pr"] = f"#{up['fix_pr']}"
    e["merge_sha"] = up["merge_sha"]
    e["test_after"] = up["evidence"]
    e["date"] = "2026-11-16"

json.dump(reg, open(PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

statuses = {}
for x in reg["entries"]:
    statuses[x["status"]] = statuses.get(x["status"], 0) + 1
print(f"total={len(reg['entries'])}; {statuses}")
