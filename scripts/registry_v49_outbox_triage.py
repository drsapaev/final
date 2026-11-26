#!/usr/bin/env python3
"""Registry v49 — cycle-30 (2026-11-23): triage of the public-booking
notification-outbox cluster (5 NOTIFYPBROUT* + NOTIFYPAYCLAIM) from the
73-item notification-checklist group. All 6 verified by direct source read
on origin/main 63d06517b: the claimed code paths are present verbatim
(outbox worker, lease claim, payment-notification endpoint)."""
import json

PATH = "docs/audit-registry/registry.json"

VERDICTS = {
    "NOTIFYPAYCLAIM-BE-001":
        ("STILL OPEN: POST /notifications/send-payment-notification takes caller-supplied "
         "amount: float + currency: str (notifications.py L421-423), checks only visit existence (404), "
         "_assert_doctor_owns_visit and patient existence — no canonical Payment/settlement verification "
         "before sending official paid-confirmation wording (amount forwarded verbatim L443-444)"),
    "NOTIFYPBROUTBATCHABORT-BE-001":
        ("RESIDUAL OPEN, narrowed: per-item delivery/completion/deferral are now individually try-wrapped "
         "with rollback+log (outbox service L60-100), but the post-claim fetch item = db.get(...) (L57) is "
         "still outside the per-item try — a session exception there still aborts the whole leased batch "
         "until lease expiry, exactly the claimed path"),
    "NOTIFYPBROUTFENCE-BE-001":
        ("STILL OPEN: _claim_due filters only lease_expires_at is None / <= now (L120-121); no owner token, "
         "fencing token or generation column anywhere in the service; _mark_completed/_defer write by row id "
         "alone and clear lease_expires_at (L153-169) — a stale worker can clear/ACK a lease re-claimed by a "
         "second worker after expiry"),
    "NOTIFYPBROUTRETRYMAX-BE-001":
        ("STILL OPEN: attempt_count increments unboundedly (L147); retry_delay_seconds only caps the backoff "
         "exponent at one hour (L25-27); no max-attempt terminal state, no dead-letter, no failure-age alert — "
         "permanent delivery failures retry forever (claim requires owner retention/replay policy decision first)"),
    "NOTIFYPBROUTSTALE-BE-001":
        ("STILL OPEN, owner-policy dependent: notify_public_booking_request receives request_version only to "
         "embed it in metadata (registrar_notification_service.py L92/L115) — no recheck of current "
         "PublicBookingRequest.status/version before delivery, so a stale v1 event can still be emitted as "
         "actionable after withdrawal/confirmation at v2 (claim itself defers the fix to an owner policy decision)"),
    "NOTIFYPBROUTWORKERFAIL-BE-001":
        ("STILL OPEN: ARQ job run_public_booking_request_notification_outbox catches Exception, logs warning "
         "and returns normally (tasks/worker.py L842-846) — batch failure never surfaces in task status, "
         "masking it from task-status-based monitoring"),
}

REVIEWER = ("registry-agent cycle-30 triage 2026-11-23: direct source read on origin/main 63d06517b "
            "(outbox service L25-171, tasks/worker.py L823-846, notifications.py L419-460, "
            "registrar_notification_service.py L92-130)")

reg = json.load(open(PATH, encoding="utf-8"))
upgraded = []
for e in reg["entries"]:
    v = VERDICTS.get(e["id"])
    if v is None:
        continue
    e["status"] = "CONFIRMED_OPEN"
    e["checked"] = True
    e["root_cause"] = v[0]
    e["test_after"] = v[0] + "; " + REVIEWER
    e["reviewer"] = REVIEWER
    e["date"] = "2026-11-23"
    upgraded.append(e["id"])

json.dump(reg, open(PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
statuses = {}
for x in reg["entries"]:
    statuses[x["status"]] = statuses.get(x["status"], 0) + 1
print(f"upgraded {len(upgraded)}: {' '.join(upgraded)}")
print(f"total={len(reg['entries'])}; {statuses}")
leftover = [e["id"] for e in reg["entries"] if e["status"] == "UNVERIFIED" and "checklist expansion (2026-11-14" in str(e.get("source", ""))]
print(f"checklist group still UNVERIFIED: {len(leftover)}")
