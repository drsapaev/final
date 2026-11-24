#!/usr/bin/env python3
"""Registry v51 — cycle-32 (2026-11-24): NOTIFYTG×8 triage of the
notification-checklist group (73 total, batch 2). All 8 verified by direct
source read on origin/main be42ec561 (bot.py L94-769, telegram_notifications.py
delivery contract, telegram_delivery_authorization.py lab_payload, admin_telegram
_settings.py webhook rotation, queue_svc/_operations.py).
3 defects verified repaired by the owner notification rework (#4076
a7e13fcb5 reshaped the patient TG delivery surface), 5 remain CONFIRMED_OPEN."""
import json

PATH = "docs/audit-registry/registry.json"

VERDICTS = {
    # ---- FIXED (3) ----
    "NOTIFYTGCHATSCOPE-BE-001": ("FIXED_VERIFIED_ON_MAIN", "#4076", "a7e13fcb5",
        "patient TG delivery no longer accepts caller chat IDs: the endpoint resolves the chat via "
        "_linked_patient_chat(db, patient_id, event_type) (telegram_notifications.py L77-80) from the "
        "patient-bound link store, adds _report_access visit-ownership checks (L102-112), finalized-report "
        "gating (409) and role denial (403), and documents the patient-bound delivery error contract (L57-61); "
        "preference gating ('disabled by patient preference') present",
        "CONFIRMED then; now server-resolved patient-bound chat + ownership"),
    "NOTIFYTGDOCTORKEY-BE-001": ("FIXED_VERIFIED_ON_MAIN", "#4076", "a7e13fcb5",
        "the bot reminder no longer renders doctor fields at all: send_appointment_reminder consumes only "
        "id/occurrence_revision/telegram_link_id/patient_link_epoch and sends a generic 'У вас новое "
        "уведомление' with a 'Просмотреть' callback (bot.py L548-568) — the mismatched AppointmentData "
        ".doctor key read is gone from the delivery path",
        "CONFIRMED then; delivery path restructured, key read removed"),
    "NOTIFYTGLABKEY-BE-001": ("FIXED_VERIFIED_ON_MAIN", "#4076", "a7e13fcb5",
        "producer and renderer keys now agree on the restructured path: lab_payload passes "
        "{'test_name': result.test_name, 'date': ...} (telegram_delivery_authorization.py L188-189; "
        "LabResult.test_name is the model attr, models/lab.py L81) and the bot renderer reads "
        "results_info.get('test_name') (bot.py L579) — the typed LabResultsData.test_type mismatch is gone; "
        "privacy minimization preserved (name+date only)",
        "CONFIRMED then; keys consistent on the restructured delivery path"),
    # ---- CONFIRMED_OPEN (5) ----
    "NOTIFYTGBOTCONFIG-BE-001": ("CONFIRMED_OPEN", None, None,
        "STILL OPEN: the legacy aiogram bot reads the startup env token only (bot.py L94: "
        "self.token = settings.TELEGRAM_BOT_TOKEN) and is independent of the DB-configured canonical "
        "patient bot token SSOT (store_patient_bot_token in admin_telegram/_settings.py)"),
    "NOTIFYTGBOTJOIN-BE-001": ("CONFIRMED_OPEN", None, None,
        "STILL OPEN verbatim: the patient queue callback calls "
        "await self.queue_service.join_queue(specialist_id=..., phone=..., telegram_id=..., patient_name=...) "
        "(bot.py L477-482) but QueueBusinessService (queue_svc package via the queue_service shim) has NO "
        "join_queue method — only join_queue_with_token (queue_svc/_operations.py L2165) — so patient "
        "queue join via the bot raises AttributeError at runtime"),
    "NOTIFYTGBOTLINKS-BE-001": ("CONFIRMED_OPEN", None, None,
        "STILL OPEN: the patient bot's 'Мои записи' handler is a stub ('Загрузка данных...') and its WebApp "
        "button opens FRONTEND_URL/appointments (bot.py L505-520) — the staff-alias URL from the claim; "
        "other buttons point at /mobile, /appointment, /lab-results"),
    "NOTIFYTGQUEUEWINDOW-BE-001": ("CONFIRMED_OPEN", None, None,
        "STILL OPEN: /queue gates on host-local datetime.now() hour 7-8 with a hardcoded RU message "
        "(bot.py L224-234); the join callback performs no queue-policy recheck on stale callbacks (and "
        "currently cannot succeed at all due to the absent join_queue method)"),
    "NOTIFYTGWEBHOOKROT-BE-001": ("CONFIRMED_OPEN", None, None,
        "STILL OPEN verbatim: webhook secret rotation posts the NEW secret to api.telegram.org/setWebhook "
        "FIRST (admin_telegram/_settings.py L382-386) and only after remote ok persists it "
        "(update_setting + update_telegram_config with webhook_secret=secret_token, L396-413) — a DB "
        "failure after remote success leaves the live webhook expecting a secret the DB never recorded"),
}

REVIEWER = ("registry-agent cycle-32 triage 2026-11-24: direct source read on origin/main be42ec561 "
            "(services/telegram/bot.py, api/v1/endpoints/telegram_notifications.py, "
            "services/telegram_delivery_authorization.py, api/v1/endpoints/admin_telegram/_settings.py, "
            "services/queue_svc/_operations.py, models/lab.py)")

reg = json.load(open(PATH, encoding="utf-8"))
upgraded = []
for e in reg["entries"]:
    v = VERDICTS.get(e["id"])
    if v is None:
        continue
    status, pr, sha, root = v[:4]
    e["status"] = status
    e["checked"] = True
    if pr:
        e["fix_pr"] = pr
        e["merge_sha"] = sha
        if not e.get("test_before"):
            e["test_before"] = str(e.get("evidence") or "")[:400]
    else:
        e["root_cause"] = root
    e["test_after"] = root + "; " + REVIEWER
    e["reviewer"] = REVIEWER
    e["date"] = "2026-11-24"
    upgraded.append(e["id"])

json.dump(reg, open(PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
statuses = {}
for x in reg["entries"]:
    statuses[x["status"]] = statuses.get(x["status"], 0) + 1
fixed = [i for i in upgraded if VERDICTS[i][0] == "FIXED_VERIFIED_ON_MAIN"]
print(f"upgraded {len(upgraded)} (FIXED {len(fixed)}, OPEN {len(upgraded)-len(fixed)})")
print("FIXED:", " ".join(sorted(fixed)))
print(f"total={len(reg['entries'])}; {statuses}")
leftover = [e["id"] for e in reg["entries"] if e["status"] == "UNVERIFIED" and "checklist expansion (2026-11-14" in str(e.get("source", ""))]
print(f"checklist group still UNVERIFIED: {len(leftover)}")
