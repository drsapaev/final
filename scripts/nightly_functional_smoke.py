#!/usr/bin/env python3
"""Nightly functional smoke — Level 1 API journey against the running backend.

Answers the question "does the clinic app actually work today?" that the
02:00 DB backup cannot answer. Runs a registrar -> doctor -> lab -> cashier ->
analytics scenario with SYNTHETIC-tagged data only (repo synthetic data policy).

Steps:
  1.  GET  /api/v1/health
  2.  login smoke_registrar / smoke_doctor (+ optional TOTP)
  3.  POST /api/v1/patients/                        (registrar)
  4.  GET  /api/v1/registrar/doctors                (registrar)
  5.  POST /api/v1/visits/visits                    (doctor)
  6.  GET  /api/v1/lab/templates                    (doctor)
  7.  POST /api/v1/lab/orders                       (doctor)
  8.  POST /api/v1/payments/                        (cashier via TOTP, optional)
  9.  GET  /api/v1/analytics/visualization/doctors/performance (doctor)
  10. GET  /api/v1/registrar/queues/today            (registrar)

M-1 (Manager deprecation): step 9 was repointed from the deprecated
Manager-role smoke account + advanced-analytics endpoint to the canonical
smoke_doctor + analytics/visualization endpoint. Coverage change: OLD
asserted privileged financial/advanced analytics endpoint availability
under the deprecated Manager role; NEW asserts the production analytics
pipeline (advanced analytics service -> visualization charts -> DB
aggregation) availability under the canonical Doctor role. Admin-only
advanced-analytics coverage lives in the backend integration suite
(test_manager_deprecation.py + test_analytics_contracts.py).

Accounts must exist first (backend/app/scripts/ensure_smoke_users.py).
Credentials come from backend/.env: SMOKE_USER_PASSWORD, optional
SMOKE_CASHIER_USERNAME / SMOKE_CASHIER_TOTP_SECRET, optional SMOKE_BASE_URL.

Exit codes: 0 = no FAIL, 2 = at least one FAIL. FAILs are also reported to
Sentry (backend DSN) so the nightly run is visible in the usual dashboard.

Usage:
    powershell -File scripts/run_python.ps1 scripts/nightly_functional_smoke.py
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import struct
import sys
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = REPO_ROOT / "backend" / ".env"
ARTIFACT_DIR = REPO_ROOT / "output" / "nightly_smoke"

REQUIRED_ENV_KEYS = ("SMOKE_USER_PASSWORD",)


# --------------------------------------------------------------------------
# env / config
# --------------------------------------------------------------------------

def load_env(path: Path) -> dict[str, str]:
    """Minimal .env parser (utf-8-sig: production .env starts with a BOM)."""
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip("'\"")
    return values


ENV = {**load_env(ENV_PATH), **{k: v for k, v in os.environ.items() if v}}

BASE_URL = (ENV.get("SMOKE_BASE_URL") or "http://127.0.0.1:18000").rstrip("/")
SMOKE_PASSWORD = ENV.get("SMOKE_USER_PASSWORD", "")
CASHIER_USERNAME = ENV.get("SMOKE_CASHIER_USERNAME", "")
CASHIER_TOTP_SECRET = ENV.get("SMOKE_CASHIER_TOTP_SECRET", "")
SENTRY_DSN = ENV.get("SENTRY_DSN", "")

RUN_TAG = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


# --------------------------------------------------------------------------
# HTTP + TOTP helpers (stdlib only — no deps on the host Python)
# --------------------------------------------------------------------------

def http(method: str, path: str, token: str | None = None, body: dict | None = None,
         timeout: int = 20) -> tuple[int, dict | list | str]:
    url = f"{BASE_URL}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", "replace")
            status = resp.status
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        status = exc.code
    except Exception as exc:  # connection refused, DNS, timeout
        return 0, {"_smoke_transport_error": str(exc)}
    try:
        return status, json.loads(raw)
    except json.JSONDecodeError:
        return status, raw[:200]


def totp_now(secret: str, step: int = 30, digits: int = 6) -> str:
    key = base64.b32decode(secret.replace(" ", "").upper() + "=" * (-len(secret.replace(" ", "")) % 8))
    counter = struct.pack(">Q", int(time.time()) // step)
    digest = hmac.new(key, counter, hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code = (struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF) % (10 ** digits)
    return str(code).zfill(digits)


def login(username: str, password: str, totp_secret: str = "") -> tuple[str | None, int | None, str]:
    """Login; returns (token, user_id, detail).

    user_id comes from the login response body itself — an extra /auth/me
    probe here used to trip the 5/5min login rate limit (429) mid-run.
    """
    status, body = http("POST", "/api/v1/authentication/login",
                        body={"username": username, "password": password})
    if status != 200 or not isinstance(body, dict):
        # intentionally no response body in details — it is not needed for
        # triage and keeps credentials/tokens out of logs and artifacts
        return None, None, f"login HTTP {status}"
    if body.get("requires_2fa_setup"):
        return None, None, "login requires 2FA enrollment (requires_2fa_setup) — smoke cannot automate enrollment"
    if body.get("requires_2fa"):
        pending = body.get("pending_2fa_token")
        if not totp_secret or not pending:
            return None, None, "login requires 2FA code and no TOTP secret is configured for this account"
        v_status, v_body = http("POST", "/api/v1/2fa/verify", body={
            "pending_2fa_token": pending, "totp_code": totp_now(totp_secret)})
        if v_status != 200 or not (isinstance(v_body, dict) and v_body.get("access_token")):
            return None, None, f"2FA verify HTTP {v_status}"
        v_user = (v_body.get("user") or {})
        return v_body["access_token"], v_user.get("id"), "ok (via TOTP)"
    token = (body.get("access_token") or "").strip()
    if not token:
        return None, None, "login HTTP 200 but no access_token in response"
    user = body.get("user") or {}
    return token, user.get("id"), "ok"


# --------------------------------------------------------------------------
# reporting
# --------------------------------------------------------------------------

RESULTS: list[dict] = []
CREATED: dict[str, object] = {}


def _mask_secrets(text: str) -> str:
    """Defense-in-depth: never echo credentials into logs or artifacts."""
    masked = text
    for secret in filter(None, (SMOKE_PASSWORD, CASHIER_TOTP_SECRET)):
        masked = masked.replace(secret, "***")
    return masked


def record(step: str, status: str, detail: str) -> None:
    detail = _mask_secrets(detail)
    RESULTS.append({"step": step, "status": status, "detail": detail})
    mark = {"PASS": "PASS", "FAIL": "FAIL", "SKIP": "SKIP"}[status]
    print(f"[{mark}] {step}: {detail}")  # codeql[py/clear-text-logging-sensitive-data] — secrets masked above; details carry no credentials


def sentry_report_failures() -> None:
    if not SENTRY_DSN or "/" not in SENTRY_DSN:
        return
    try:
        # public key + host + project id from the DSN
        after_scheme = SENTRY_DSN.split("://", 1)[1]
        key, rest = after_scheme.split("@", 1)
        host, project = rest.split("/", 1)
        url = f"https://{host}/api/{project}/envelope/"
        for item in RESULTS:
            if item["status"] != "FAIL":
                continue
            event_id = uuid.uuid4().hex
            envelope = (
                json.dumps({"event_id": event_id, "dsn": SENTRY_DSN}) + "\n"
                + json.dumps({
                    "event_id": event_id,
                    "timestamp": time.time(),
                    "platform": "python",
                    "level": "error",
                    "logger": "nightly-functional-smoke",
                    "environment": ENV.get("SENTRY_ENV", "production"),
                    "message": f"nightly smoke FAIL: {item['step']} — {item['detail'][:180]}",
                    "tags": {"smoke_step": item["step"], "run": RUN_TAG},
                }) + "\n"
            )
            req = urllib.request.Request(url, data=envelope.encode(), method="POST")
            req.add_header("Content-Type", "application/x-sentry-envelope")
            req.add_header("X-Sentry-Auth",
                           f"Sentry sentry_key={key}, sentry_version=7, sentry_client=nightly-smoke/1.0")
            try:
                urllib.request.urlopen(req, timeout=10).read()
            except Exception:
                pass  # never let reporting break the run
    except Exception:
        pass


def write_artifact() -> Path:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    path = ARTIFACT_DIR / f"smoke-{RUN_TAG}.json"
    path.write_text(json.dumps({
        "run": RUN_TAG,
        "base_url": BASE_URL,
        "results": RESULTS,
        "created_synthetic_records": CREATED,
        "note": "all records tagged SYNTHETIC-SMOKE; safe to purge by doc_number prefix",
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


# --------------------------------------------------------------------------
# scenario
# --------------------------------------------------------------------------

def main() -> int:
    print(f"Nightly functional smoke — {RUN_TAG} UTC — target {BASE_URL}")
    print("=" * 70)

    missing = [k for k in REQUIRED_ENV_KEYS if not ENV.get(k)]
    if missing:
        print(f"ABORT: missing env keys in {ENV_PATH}: {missing}")
        return 2

    tokens: dict[str, str] = {}

    # 1. health ------------------------------------------------------------
    status, body = http("GET", "/api/v1/health")
    record("health", "PASS" if status == 200 else "FAIL",
           f"GET /api/v1/health -> {status}")

    # 2. logins ------------------------------------------------------------
    accounts = [
        ("smoke_registrar", ""),
        ("smoke_doctor", ""),
    ]
    if CASHIER_USERNAME and CASHIER_TOTP_SECRET:
        accounts.append((CASHIER_USERNAME, CASHIER_TOTP_SECRET))
    user_ids: dict[str, int | None] = {}
    for username, secret in accounts:
        token, uid, detail = login(username, SMOKE_PASSWORD, secret)
        tokens[username] = token or ""
        user_ids[username] = uid
        record(f"login {username}", "PASS" if token else "FAIL", detail)

    reg = tokens.get("smoke_registrar", "")
    doc = tokens.get("smoke_doctor", "")

    # 3. patient create (registrar) ----------------------------------------
    patient_id = None
    # phone must be unique per run: backend enforces patient phone uniqueness
    run_digits = RUN_TAG.replace("-", "")
    status, body = http("POST", "/api/v1/patients/", token=reg, body={
        "last_name": f"SYNTHETIC-SMOKE-{RUN_TAG}",
        "first_name": "Nightly",
        "phone": f"+998{run_digits[-9:]}",
        "doc_type": "passport",
        "doc_number": f"SMOKE{RUN_TAG.replace('-', '')}",
        "birth_date": "1990-01-01",
        "address": "SYNTHETIC-SMOKE address — nightly smoke artifact",
    })
    if status in (200, 201) and isinstance(body, dict):
        patient_id = body.get("id")
        CREATED["patient_id"] = patient_id
        record("patient create", "PASS", f"id={patient_id}")
    else:
        record("patient create", "FAIL", f"HTTP {status}: {json.dumps(body, ensure_ascii=False)[:200]}")

    # 4. doctors list (registrar) ------------------------------------------
    doctor_id = None
    doctor_user_id = user_ids.get("smoke_doctor")
    status, body = http("GET", "/api/v1/registrar/doctors", token=reg)
    if status == 200:
        entries = body if isinstance(body, list) else (
            body.get("doctors") or body.get("items") or body.get("data") or [] if isinstance(body, dict) else [])
        # The visits write-guard requires the ACTING doctor's own active
        # profile: pick the smoke doctor's row, not just the first one.
        own = next(
            (e for e in entries if isinstance(e, dict)
             and doctor_user_id is not None and e.get("user_id") == doctor_user_id),
            None,
        )
        if own is not None:
            doctor_id = own.get("id") or own.get("doctor_id")
        if doctor_id is not None:
            record("doctors list", "PASS", f"smoke doctor profile id={doctor_id}")
        elif entries:
            record("doctors list", "FAIL",
                   "smoke_doctor has no active Doctor profile — run ensure_smoke_users")
        else:
            record("doctors list", "FAIL",
                   f"HTTP 200 but no doctor rows found — production has no doctors? body={json.dumps(body, ensure_ascii=False)[:160]}")
    else:
        record("doctors list", "FAIL", f"HTTP {status}: {json.dumps(body, ensure_ascii=False)[:200]}")

    # 5. visit create (doctor) ---------------------------------------------
    visit_id = None
    if patient_id is None or doctor_id is None:
        record("visit create", "SKIP", "needs patient_id and doctor_id from earlier steps")
    else:
        status, body = http("POST", "/api/v1/visits/visits", token=doc, body={
            "patient_id": patient_id,
            "doctor_id": doctor_id,
            "notes": "SYNTHETIC-SMOKE nightly visit",
        })
        if status in (200, 201) and isinstance(body, dict):
            visit_id = body.get("id")
            CREATED["visit_id"] = visit_id
            record("visit create", "PASS", f"id={visit_id}")
        else:
            record("visit create", "FAIL", f"HTTP {status}: {json.dumps(body, ensure_ascii=False)[:200]}")

    # 6. lab templates (doctor) --------------------------------------------
    template_id = None
    status, body = http("GET", "/api/v1/lab/templates", token=doc)
    if status == 200 and isinstance(body, list):
        if body and isinstance(body[0], dict):
            template_id = body[0].get("id")
            record("lab templates", "PASS", f"{len(body)} templates, first id={template_id}")
        else:
            record("lab templates", "SKIP",
                   "no lab templates exist — lab catalog empty in this deployment (consider seeding)")
    else:
        record("lab templates", "FAIL", f"HTTP {status}: {json.dumps(body, ensure_ascii=False)[:200]}")

    # 7. lab order create (doctor) -----------------------------------------
    if template_id is None or patient_id is None:
        record("lab order create", "SKIP", "needs template_id and patient_id")
    else:
        status, body = http("POST", "/api/v1/lab/orders", token=doc, body={
            "template_id": template_id,
            "patient_id": patient_id,
            "visit_id": visit_id,
            "notes": "SYNTHETIC-SMOKE nightly order",
        })
        if status in (200, 201) and isinstance(body, dict):
            CREATED["lab_instance_id"] = body.get("instance_id")
            record("lab order create", "PASS", f"instance_id={body.get('instance_id')}")
        else:
            record("lab order create", "FAIL", f"HTTP {status}: {json.dumps(body, ensure_ascii=False)[:200]}")

    # 8. payment create (cashier — 2FA-protected role) ----------------------
    cashier_token = tokens.get(CASHIER_USERNAME, "") if CASHIER_USERNAME else ""
    if not cashier_token:
        record("payment create", "SKIP",
               "cashier is a mandatory-2FA role; set SMOKE_CASHIER_USERNAME + "
               "SMOKE_CASHIER_TOTP_SECRET in backend/.env to enable this step")
    elif visit_id is None:
        record("payment create", "SKIP", "needs visit_id from earlier step")
    else:
        status, body = http("POST", "/api/v1/payments/", token=cashier_token, body={
            "visit_id": visit_id,
            "amount": 1000,
            "currency": "UZS",
            "method": "cash",
            "note": "SYNTHETIC-SMOKE nightly payment",
        })
        if status in (200, 201) and isinstance(body, dict):
            CREATED["payment_id"] = body.get("payment_id") or body.get("id")
            record("payment create", "PASS", f"id={CREATED.get('payment_id')}")
        else:
            record("payment create", "FAIL", f"HTTP {status}: {json.dumps(body, ensure_ascii=False)[:200]}")

    # 9. doctor performance analytics (doctor) ----------------------------
    # M-1: repointed from the deprecated Manager account + /analytics/
    # advanced/doctors/performance to the canonical doctor-authorized
    # visualization surface. See the module docstring for the recorded
    # coverage change.
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    status, body = http(
        "GET",
        f"/api/v1/analytics/visualization/doctors/performance?start_date={today}&end_date={today}",
        token=doc,
    )
    record("analytics doctors/performance", "PASS" if status == 200 else "FAIL",
           f"GET -> {status}" + ("" if status == 200 else " (doctors analytics endpoint broken?)"))

    # 10. queue today (registrar) ------------------------------------------
    status, body = http("GET", "/api/v1/registrar/queues/today", token=reg)
    record("queue today", "PASS" if status == 200 else "FAIL",
           f"GET /api/v1/registrar/queues/today -> {status}")

    # summary ---------------------------------------------------------------
    fails = [r for r in RESULTS if r["status"] == "FAIL"]
    skips = [r for r in RESULTS if r["status"] == "SKIP"]
    print("=" * 70)
    print(f"TOTAL: {len(RESULTS)} steps | PASS {len(RESULTS) - len(fails) - len(skips)} "
          f"| FAIL {len(fails)} | SKIP {len(skips)}")
    artifact = write_artifact()
    print(f"Artifact: {artifact}")
    if fails:
        print("FAILED steps:")
        for item in fails:
            print(f"  - {item['step']}: {item['detail']}")
        sentry_report_failures()
    return 2 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
