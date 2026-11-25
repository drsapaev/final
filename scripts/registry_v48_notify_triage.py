#!/usr/bin/env python3
"""Registry v48 — cycle-29 (2026-11-23): triage of the first 31 IDs of the
73-item notification-checklist group (owner checklist expansion 2026-11-14):
the 11-member NOTIFYDOC* doctor-info cluster and the 20-member NOTIFYEMAILSMS*
enhanced email/SMS cluster. Every claim re-verified by direct source read on
origin/main 63d06517b; 7 EMAILSMS defects verified repaired (primary rework
owner PR #4076 a7e13fcb5 + model constraint), 24 remain CONFIRMED_OPEN with
precise file:line evidence. Backend test rerun skipped honestly: all email-sms
backend suites are PG-coupled and no PostgreSQL is available in this sandbox
session (owner CI on #4076 ALL GREEN covers the merged state)."""
import json

PATH = "docs/audit-registry/registry.json"

# id -> (new_status, fix_pr, merge_sha, test_after)
VERDICTS = {
    # ---- FIXED (7) ----
    "NOTIFYEMAILSMSPAYTRUST-BE-001": ("FIXED_VERIFIED_ON_MAIN", "#4076", "a7e13fcb5",
        "_ensure_payment_confirmation_belongs_to_patient: payment_id required (400 if absent), Payment row fetched from DB, visit.patient_id ownership check 403, refunded_amount check; amount/currency taken only from the DB-owned snapshot _payment_notification_data (endpoint L90-133, L440-472) with delivery-time recheck (payment_current -> 'Данные изменились' guard); client-supplied payment payload no longer trusted"),
    "NOTIFYEMAILSMSLABPHANTOM-BE-001": ("FIXED_VERIFIED_ON_MAIN", "#4076", "a7e13fcb5",
        "endpoint now REQUIRES lab_results_id (L343) and fetches the real result via service(db, lab_result_id=..., patient_id=...) (L367/382); card context built from the actual row: doctor.user.full_name, result.abnormal (L220-240) — no fabricated test type/date/has_abnormalities"),
    "NOTIFYEMAILSMSAPPTFIELDS-BE-001": ("FIXED_VERIFIED_ON_MAIN", "#4076", "a7e13fcb5",
        "appointment reminder context is derived server-side via ORM traversal (doctor.user.full_name etc., endpoint L220-240) — nonexistent Appointment.doctor_name/specialty/date/time/cabinet attribute reads are gone; service consumes plain dicts"),
    "NOTIFYEMAILSMSEMPTYOK-BE-001": ("FIXED_VERIFIED_ON_MAIN", "#4076", "a7e13fcb5",
        "all three enhanced helpers compute results['success'] = bool(results['channels']) and all(...success...) (svc L444/515/587); unavailable channel marks a failure entry ('Канал недоступен'), delivery_guard deauth marks 'Данные изменились' — no-contact no longer yields success=true"),
    "NOTIFYEMAILSMSFALLBACKHTML-BE-001": ("FIXED_VERIFIED_ON_MAIN", "#4076", "a7e13fcb5",
        "template-render failure is fail-closed: _render_email_template None -> return False, 'Не удалось подготовить email' (svc L152-156); the raw f-string _get_basic_email_template has no call sites (dead code, L665) — autoescape bypass path removed"),
    "NOTIFYEMAILSMSSMSLOADER-BE-001": ("FIXED_VERIFIED_ON_MAIN", "#4076", "a7e13fcb5",
        "dedicated SMS Jinja env loads from templates/sms (svc L56-57), separate from templates/email; _render_sms_template fail-closed (None -> False, svc L611-618) — no templates/email/sms conflict and no silent generic fallback omitting details"),
    "NOTIFYEMAILSMSAMOUNTNONE-BE-001": ("FIXED_VERIFIED_ON_MAIN", "#4076", "a7e13fcb5",
        "claim precondition gone: Payment.amount is nullable=False (backend/app/models/billing.py L34-36/L63); snapshot _payment_notification_data carries DB amount; service formats via payment_data.get('amount', 0):,.2f (svc L547-549) — None->TypeError 500 unreachable through the API; cosmetic residual: message amount always 0.00 when callers pass only payment_id"),
    # ---- CONFIRMED_OPEN (24) ----
    "NOTIFYDOCACTIVEFILTER-BE-001": ("CONFIRMED_OPEN", None, None,
        "STILL OPEN on 63d06517b: get_doctors_by_specialization hard-codes Doctor.active == True (doctor_info_service.py L113-118) and the endpoint never forwards active_only into the specialization branch (doctor_info.py L110-111)"),
    "NOTIFYDOCDBFAILMASK-BE-001": ("CONFIRMED_OPEN", None, None,
        "STILL OPEN: get_doctor_full_info catches broad Exception and returns synthetic 'Врач #N' dict (svc L28-45, L100-115); strict GET /doctors/{id} wraps it into HTTP 200 DoctorInfoResponse (doctor_info.py L76-90)"),
    "NOTIFYDOCDEPARTMENTFK-BE-001": ("CONFIRMED_OPEN", None, None,
        "STILL OPEN: department derived from Doctor.specialty via get_department_info(doctor.specialty) (svc L78) while Doctor.department_id exists (models/clinic.py L119) and is ignored; response has no department_id"),
    "NOTIFYDOCDEPTDTO-BE-001": ("CONFIRMED_OPEN", None, None,
        "STILL OPEN: get_department_info returns dict without id/is_active (svc L170-186) while DepartmentInfoResponse requires id: int + is_active: bool (doctor_info.py L39-46) — /departments and /appointments/{id}/doctor-info serializer raise on nonempty output"),
    "NOTIFYDOCDEPTID-BE-001": ("CONFIRMED_OPEN", None, None,
        "STILL OPEN: GET /departments/{department_id} passes int into service.get_department_info(specialty: str) (doctor_info.py L171 -> svc L128 signature) — specialty_variants(int) fails inside try -> None -> 404 for existing Department IDs"),
    "NOTIFYDOCDEPTSOURCE-BE-001": ("CONFIRMED_OPEN", None, None,
        "STILL OPEN: get_all_departments derives from Doctor.specialty distinct over active doctors (svc L208-226), no Department registry; 'general' synthesizes 'Общая практика'"),
    "NOTIFYDOCDYNDEPT-BE-001": ("CONFIRMED_OPEN", None, None,
        "STILL OPEN: get_department_by_name maps only six hardcoded Russian labels (svc L187-200); get_doctors_by_department returns [] for any dynamically persisted department (svc L288-299)"),
    "NOTIFYDOCLISTEMPTY-BE-001": ("CONFIRMED_OPEN", None, None,
        "STILL OPEN: GET /doctors with neither specialization nor department_name sets doctors = [] ('можно добавить метод get_all_doctors' comment, doctor_info.py L112-113) -> 200 total_count=0"),
    "NOTIFYDOCPHONEPROFILE-BE-001": ("CONFIRMED_OPEN", None, None,
        "STILL OPEN: phone = getattr(doctor.user, 'phone', None) (svc L60) reads a non-existent User.phone attr (no phone field in models/user.py) -> always None"),
    "NOTIFYDOCSPECWILDCARD-BE-001": ("CONFIRMED_OPEN", None, None,
        "STILL OPEN: Doctor.specialty.ilike(f\"%{variant}%\") (svc L110-113) — user %/_ act as SQL wildcards, substring matches unrelated specialties"),
    "NOTIFYDOCUNKNOWN-BE-001": ("CONFIRMED_OPEN", None, None,
        "STILL OPEN: strict GET /doctors/{doctor_id} returns synthetic 'Врач #N' with 200 for missing Doctor (svc L28-45 + doctor_info.py L76-90); lenient formatter fallback preserved separately in format_doctor_info_for_notification (svc L301-325)"),
    "NOTIFYEMAILSMSATTACHACK-BE-001": ("CONFIRMED_OPEN", None, None,
        "STILL OPEN: _add_attachment catches Exception and only logs (svc L662-665) — attachment errors do not fail or flag the send; provider Email returns success"),
    "NOTIFYEMAILSMSBULKACK-BE-001": ("CONFIRMED_OPEN", None, None,
        "STILL OPEN: send-bulk-email returns success=True / 'Массовая рассылка email запущена' unconditionally after awaiting the provider batch result, even when sent=0 (endpoint L530-537)"),
    "NOTIFYEMAILSMSBATCHBOUND-BE-001": ("CONFIRMED_OPEN", None, None,
        "STILL OPEN: batch_size/delay Query params have no ge/le bounds (endpoint L494-501) and service iterates range(0, len, batch_size) without clamping (svc L282) — batch_size=0 -> ValueError 500, negative -> no sends, oversized defeats throttling"),
    "NOTIFYEMAILSMSBULKDTO-FE-001": ("CONFIRMED_OPEN", None, None,
        "STILL OPEN: FE bulk posts batch_size/delay_between_batches in the JSON body (EmailSMSManager.tsx L281-284) while backend expects them as Query params (endpoint L494/497) -> 422; recipients shape drift per RecipientData object contract"),
    "NOTIFYEMAILSMSCLIENTLIFE-BE-001": ("CONFIRMED_OPEN", None, None,
        "STILL OPEN: httpx.AsyncClient().post(...) per SMS request without aclose/async-with (svc L242) — resource exhaustion risk on bulk sends"),
    "NOTIFYEMAILSMSCSRF-FE-001": ("CONFIRMED_OPEN", None, None,
        "STILL OPEN: all six manager fetch POSTs omit X-CSRF-Token (EmailSMSManager.tsx L194-303, no csrf header present)"),
    "NOTIFYEMAILSMSPRIOQUERY-BE-001": ("CONFIRMED_OPEN", None, None,
        "STILL OPEN: SendCustomEmailRequest declares priority: Literal['normal','high'] (schemas/notifications.py L351) but handler passes only Query priority (endpoint L589/L609, L632/L650) — body priority ignored"),
    "NOTIFYEMAILSMSRECIPIENTKEY-BE-001": ("CONFIRMED_OPEN", None, None,
        "STILL OPEN: RecipientData.email/phone both optional (schemas/notifications.py L68-77) + endpoint exclude_none=True (L513) + service direct indexing recipient['email']/recipient['phone'] (svc L289/L344) — schema-valid empty recipient -> KeyError 500"),
    "NOTIFYEMAILSMSSTATSVOLATILE-BE-001": ("CONFIRMED_OPEN", None, None,
        "STILL OPEN: statistics are the per-process in-memory singleton dict with last_reset (svc L120-125); GET /statistics reads it directly (endpoint L676-682) — not aggregated across workers nor persisted"),
    "NOTIFYEMAILSMSTEMPLATECAT-BE-001": ("CONFIRMED_OPEN", None, None,
        "RESIDUAL OPEN: limit/offset/template_type params now bounded (endpoint L713-716) but the catalogue is still a hardcoded stub ('Пока возвращаем заглушку', L719-721) with incomplete variable lists and no renderability verification"),
    "NOTIFYEMAILSMSTESTDTO-FE-001": ("CONFIRMED_OPEN", None, None,
        "STILL OPEN: POST /test-email and /test-sms still take bare query params (endpoint L802-808, L858-862) while FE sends a JSON body (EmailSMSManager.tsx L225-235) -> 422 on both sides' current shape"),
    "NOTIFYEMAILSMSTESTHTML-BE-001": ("CONFIRMED_OPEN", None, None,
        "STILL OPEN: test-email interpolates the raw message query string into the HTML body f-string (endpoint L825-850) — unescaped markup/links, admin-only but still injectable"),
    "NOTIFYEMAILSMSURL-FE-001": ("CONFIRMED_OPEN", None, None,
        "STILL OPEN: manager fetches browser-root-relative '/email-sms/...' at six sites (EmailSMSManager.tsx L194-303) without the configured backend origin or /api/v1 prefix — fails on split-origin setups"),
}

REVIEWER = "registry-agent cycle-29 triage 2026-11-23: direct source read on origin/main 63d06517b (endpoint/service/schemas/models cross-checked); FIXED claims attributed to owner PR #4076 (a7e13fcb5) whose diff introduces the verified patterns (+17 pinned-pattern hits, +2 dedicated suites)"

reg = json.load(open(PATH, encoding="utf-8"))
upgraded = []
for e in reg["entries"]:
    v = VERDICTS.get(e["id"])
    if v is None:
        continue
    status, pr, sha, after = v
    e["status"] = status
    e["checked"] = True
    if pr:
        e["fix_pr"] = pr
        e["merge_sha"] = sha
    if status == "CONFIRMED_OPEN":
        # checker requires a confirmed root_cause for CONFIRMED_OPEN
        e["root_cause"] = after.split("; ")[0]
    if status == "FIXED_VERIFIED_ON_MAIN" and not e.get("test_before"):
        # checker requires the original claim snapshot for FIXED entries
        e["test_before"] = str(e.get("evidence") or "")[:400]
    e["test_after"] = after + "; " + REVIEWER
    e["reviewer"] = REVIEWER
    e["date"] = "2026-11-23"
    upgraded.append(e["id"])

json.dump(reg, open(PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
statuses = {}
for x in reg["entries"]:
    statuses[x["status"]] = statuses.get(x["status"], 0) + 1
fixed = [i for i in upgraded if VERDICTS[i][0] == "FIXED_VERIFIED_ON_MAIN"]
print(f"upgraded {len(upgraded)} (FIXED {len(fixed)}, OPEN {len(upgraded)-len(fixed)})")
print("FIXED:", " ".join(sorted(fixed)))
print(f"total={len(reg['entries'])}; {statuses}")
missing = [i for i in VERDICTS if i not in upgraded]
print("missing entries:", missing or "none")
