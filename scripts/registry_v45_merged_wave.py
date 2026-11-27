#!/usr/bin/env python3
"""Registry v45 — cycle-27: owner merged the agent fix wave #4074/#4075/#4076/#4077
(12 agent IDs) + owner DERMAHIST fixes #4115/#4227. All re-verified on exact main
d7e23cec5: backend 12 suites 169 passed/15 skipped (PG-only), frontend 16/16."""
import json

PATH = "docs/audit-registry/registry.json"

MERGES = {
    "4074": {
        "sha": "ed1e036718d9491e27b65f5aa5810230fb6153dd",
        "title": "fix(notifications): atomic template activation and safe rendering",
        "ids": ["NOTIFYTPLACTIVECLASH-BE-001", "NOTIFYTPLPLAINTEXTESC-BE-001", "NOTIFYTPLRENDERFAIL-BE-001"],
        "tests": "test_notification_template_atomic_pg.py (339 lines), test_notification_template_render_security.py (449), test_database_exception_privacy.py (54)",
        "tb": "pre-merge state: non-atomic template activation (clash on activate), plaintext interpolation escaping gap and render-failure handling in the notification template plane (agent source review, gated fix PR #4074)",
    },
    "4075": {
        "sha": "c254bc110e097afeac6bba0b25f430ca4734c718",
        "title": "fix(auth): protect activation and password recovery",
        "ids": ["ACTIVATION-BE-001", "ACTIVATION-BE-002", "PASSRESET-BE-001", "PASSRESET-BE-002", "PASSRESET-BE-003"],
        "tests": "test_activation_concurrency_pg.py (228), test_activation_security.py (159), test_openapi_reset_activation_contract.py (28)",
        "tb": "pre-merge state: unauthenticated activation/verify-phone surface and password-recovery enumeration/throttling gaps (agent source review, gated fix PR #4075, resynced onto live main in r6)",
    },
    "4076": {
        "sha": "a7e13fcb5c0693563af53bee4e7edff69a7ebec7",
        "title": "fix(notifications): secure patient delivery and confirmations",
        "ids": ["NOTIFYTGFALSEACK-BE-001", "NOTIFYTGMARKDOWN-BE-001", "NOTIFYTGREMINDCB-BE-001"],
        "tests": "test_visit_confirmation_service.py, test_notification_platform_contract.py, confirmation-split-flow concurrency suites",
        "tb": "pre-merge state: false-positive Telegram delivery ACKs, markdown injection in patient messages and reminder-callback trust gaps (agent source review, gated fix PR #4076)",
    },
    "4077": {
        "sha": "933b1fe1fe83fc60ee6ab5825e775dec84abfd35",
        "title": "fix(auth): secure legacy and canonical password reset",
        "ids": ["WEBAUTHN-BE-001"],
        "tests": "test_legacy_password_reset_security.py (301), test_auth_plane_group33_fixes.py, test_auth_epoch_writers*.py",
        "tb": "pre-merge state: legacy password-reset path compatibility + token epoch handling gaps (agent source review, gated fix PR #4077)",
    },
    "4115": {
        "sha": "7da8323bba50819ed7e4efdc63c2ac414ba151ce",
        "title": "fix(dermahist): canonical skin-examination history keeps lesion localization (DERMAHIST-BE-001)",
        "ids": ["DERMAHIST-BE-001"],
        "tests": "test_derma_history_localization_projection.py (113)",
        "tb": "pre-merge state (owner group118/119): dermatology history schema→projection→DTO pipeline lost lesion localization for newly projected payloads; owner's own repair, verified independently in owner group120 with exact-head Unified CI 43893450904",
    },
    "4227": {
        "sha": "2e4937772d94bd64637e5d17fdab2ac01c1add7d",
        "title": "fix(dermahist): persisted EMR refreshes the same-patient history (DERMAHIST-FE-003)",
        "ids": ["DERMAHIST-FE-003"],
        "tests": "useDermatologyPatientHistory.reload.test.tsx (106), DermatologistPanel.historyReload.contract.test.tsx (59), DoctorPanels.contract.test.tsx",
        "tb": "pre-merge state: the same-patient dermatology history tab did not refresh after an EMR persist, showing stale skin-examination entries (agent fix PR #4086 proposed; owner implemented independently in #4227 — #4086 is superseded)",
    },
}

REVIEWER = "registry-agent merged-fix re-verification 2026-11-17 (exact main d7e23cec5: backend 12 suites 169 passed/15 skipped PG-only + frontend DERMAHIST 16/16)"

reg = json.load(open(PATH, encoding="utf-8"))
by_id = {e["id"]: e for e in reg["entries"]}

upgraded = []
for pr, info in MERGES.items():
    for tid in info["ids"]:
        e = by_id.get(tid)
        if e is None:
            raise SystemExit(f"MISSING registry entry: {tid}")
        e["status"] = "FIXED_VERIFIED_ON_MAIN"
        e["fix_pr"] = f"#{pr}"
        e["merge_sha"] = info["sha"]
        if not e.get("test_before"):
            e["test_before"] = info["tb"]
        e["test_after"] = (
            f"owner merge #{pr} ({info['sha'][:9]}: {info['title']}); regression suites {info['tests']}; "
            f"registry-agent re-verification on exact main d7e23cec5 (2026-11-17): backend batch 12 suites "
            f"169 passed/15 skipped (PG-only) + frontend DERMAHIST batch 16/16 — all GREEN"
        )
        e["reviewer"] = REVIEWER
        e["date"] = "2026-11-17"
        upgraded.append(tid)

json.dump(reg, open(PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
statuses = {}
for x in reg["entries"]:
    statuses[x["status"]] = statuses.get(x["status"], 0) + 1
print(f"upgraded {len(upgraded)}: {', '.join(upgraded)}")
print(f"total={len(reg['entries'])}; {statuses}")
