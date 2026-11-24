#!/usr/bin/env python3
"""Registry v44b — fill mandatory test_before for the three v44 upgrades
(schema checker requires non-empty test_before for FIXED_VERIFIED_ON_MAIN)."""
import json

PATH = "docs/audit-registry/registry.json"

TEST_BEFORE = {
    "DERMAAI-FE-002": (
        "pre-merge state (owner group109): invalid skin AI response envelope (missing/non-"
        "canonical root fields) was not rejected client-side — gallery rendered a broken AI "
        "photo analysis result; no checked-in regression existed before owner merge #4105"
    ),
    "DERMACOMPLETE-FE-001": (
        "pre-merge state (owner group109 lane): derma visit completion did not honour the "
        "shared EMR dirty registry — a dirty EMR could be bypassed by the completion ACK "
        "path; no behavioral regression existed before owner merge #4109"
    ),
    "QUEUEPRINT-FE-003": (
        "pre-merge state (owner group97 code-review): panel print fabricated ticket identity "
        "from unrelated record PKs; agent fail-first variant existed in PR #4095 but was not "
        "merged; no checked-in regression before owner merge #4114"
    ),
}

reg = json.load(open(PATH, encoding="utf-8"))
by_id = {e["id"]: e for e in reg["entries"]}

for tid, tb in TEST_BEFORE.items():
    e = by_id[tid]
    if not e.get("test_before"):
        e["test_before"] = tb

json.dump(reg, open(PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print("test_before filled:", ", ".join(TEST_BEFORE))
