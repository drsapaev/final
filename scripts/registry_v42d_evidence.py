#!/usr/bin/env python3
"""Registry v42d — cycle-24: independent verification evidence for owner merges #4102/#4104 on exact main 3b25b03e6."""
import json

PATH = "docs/audit-registry/registry.json"

reg = json.load(open(PATH, encoding="utf-8"))
by_id = {e["id"]: e for e in reg["entries"]}

EV = {
    "NOTIFYLIVEAUTH-BE-001": (
        "2026-11-16 registry-agent recheck on exact main 3b25b03e6: owner residual fix #4102 (e3addd044, "
        "websocket_auth.py live re-authorization observes fresh principal attributes) + test_websocket_auth_identity_freshness.py 3/3 GREEN"
    ),
    "DERMARX-FE-004": (
        "2026-11-16 registry-agent recheck on exact main 3b25b03e6: owner test-pin #4104 (3b25b03e6) — "
        "DermatologistPanel.deferredRxSave.test.tsx present, 4/4 GREEN across both #4104 files"
    ),
    "DERMAURL-FE-002": (
        "2026-11-16 registry-agent recheck on exact main 3b25b03e6: owner test-pin #4104 (3b25b03e6) — "
        "DermatologistPanel.deferredDeepLink.test.tsx present, 4/4 GREEN across both #4104 files"
    ),
}

for tid, note in EV.items():
    e = by_id[tid]
    e["test_after"] = (e.get("test_after") or "") + " | " + note
    e["date"] = "2026-11-16"

json.dump(reg, open(PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print("v42d evidence appended:", list(EV))
