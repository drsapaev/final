from __future__ import annotations

import json
import os
import re
import time
from datetime import date
from pathlib import Path

import psycopg
import requests
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


API_BASE = os.getenv("DOC02_API_BASE", "http://127.0.0.1:18005")
WEB_BASE = os.getenv("DOC02_WEB_BASE", "http://127.0.0.1:8080")
DATABASE_URL = os.getenv(
    "DOC02_DATABASE_URL",
    "postgresql://clinic:clinicpwd@localhost:5432/clinicdb",
)

DOCTOR_USERNAME = "doctor@example.com"
DOCTOR_PASSWORD = "doctor123"
DOCTOR_USER_ID = 21

ARTIFACT_DIR = Path(__file__).resolve().parent
BEFORE_SCREENSHOT = ARTIFACT_DIR / "doc-02-before-call.png"
AFTER_SCREENSHOT = ARTIFACT_DIR / "doc-02-after-call.png"
RESULT_JSON = ARTIFACT_DIR / "doc-02-live-verification.json"


def wait_for_http(url: str, timeout_seconds: int = 90) -> None:
    deadline = time.time() + timeout_seconds
    last_error = None
    while time.time() < deadline:
        try:
            response = requests.get(url, timeout=5)
            if response.ok:
                return
            last_error = f"{url} -> {response.status_code}"
        except Exception as exc:  # pragma: no cover - harness guard
            last_error = str(exc)
        time.sleep(1)
    raise RuntimeError(f"Timed out waiting for {url}: {last_error}")


def ensure_general_queue_dataset() -> dict[str, object]:
    stamp = int(time.time())
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select id
                from doctors
                where user_id = %s and specialty = 'general'
                order by id asc
                limit 1
                """,
                (DOCTOR_USER_ID,),
            )
            row = cur.fetchone()
            if row:
                doctor_id = row[0]
                cur.execute(
                    """
                    update doctors
                    set active = true,
                        cabinet = coalesce(cabinet, '101')
                    where id = %s
                    """,
                    (doctor_id,),
                )
            else:
                cur.execute(
                    """
                    insert into doctors (
                        user_id,
                        specialty,
                        cabinet,
                        start_number_online,
                        max_online_per_day,
                        active
                    )
                    values (%s, 'general', '101', 1, 15, true)
                    returning id
                    """,
                    (DOCTOR_USER_ID,),
                )
                doctor_id = cur.fetchone()[0]

            today = date.today()
            cur.execute(
                """
                select id
                from daily_queues
                where day = %s
                  and specialist_id = %s
                  and coalesce(queue_tag, 'general') = 'general'
                order by id asc
                limit 1
                """,
                (today, doctor_id),
            )
            row = cur.fetchone()
            if row:
                queue_id = row[0]
                cur.execute(
                    """
                    update daily_queues
                    set active = true,
                        queue_tag = 'general',
                        online_start_time = '07:00',
                        online_end_time = '09:00',
                        max_online_entries = 15
                    where id = %s
                    """,
                    (queue_id,),
                )
            else:
                cur.execute(
                    """
                    insert into daily_queues (
                        day,
                        specialist_id,
                        queue_tag,
                        active,
                        online_start_time,
                        online_end_time,
                        max_online_entries
                    )
                    values (%s, %s, 'general', true, '07:00', '09:00', 15)
                    returning id
                    """,
                    (today, doctor_id),
                )
                queue_id = cur.fetchone()[0]

            cur.execute(
                """
                update queue_entries
                set status = 'served'
                where queue_id = %s
                  and status = 'waiting'
                """,
                (queue_id,),
            )

            cur.execute(
                """
                select id, first_name, last_name, phone
                from patients
                order by id desc
                limit 1
                """
            )
            patient_id, first_name, last_name, phone = cur.fetchone()
            patient_name = f"DOC-02 {last_name} {stamp}"

            cur.execute(
                """
                select coalesce(max(number), 0) + 1
                from queue_entries
                where queue_id = %s
                """,
                (queue_id,),
            )
            number = cur.fetchone()[0]

            cur.execute(
                """
                insert into queue_entries (
                    queue_id,
                    number,
                    patient_id,
                    patient_name,
                    phone,
                    visit_type,
                    discount_mode,
                    total_amount,
                    source,
                    status,
                    queue_time,
                    priority,
                    session_id
                )
                values (
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    'paid',
                    'none',
                    0,
                    'desk',
                    'waiting',
                    now(),
                    0,
                    %s
                )
                returning id
                """,
                (queue_id, number, patient_id, patient_name, phone, f"doc-02-{stamp}"),
            )
            entry_id = cur.fetchone()[0]
        conn.commit()

    return {
        "doctor_id": doctor_id,
        "queue_id": queue_id,
        "entry_id": entry_id,
        "patient_id": patient_id,
        "patient_name": patient_name,
        "phone": phone,
        "number": number,
    }


def login_doctor() -> tuple[str, dict[str, object]]:
    response = requests.post(
        f"{API_BASE}/api/v1/authentication/login",
        json={"username": DOCTOR_USERNAME, "password": DOCTOR_PASSWORD},
        timeout=15,
    )
    response.raise_for_status()
    token = response.json()["access_token"]

    me = requests.get(
        f"{API_BASE}/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    me.raise_for_status()
    return token, me.json()


def fetch_queue_state(token: str) -> dict[str, object]:
    response = requests.get(
        f"{API_BASE}/api/v1/doctor/general/queue/today",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    response.raise_for_status()
    return response.json()


def write_result(payload: dict[str, object]) -> None:
    RESULT_JSON.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def run_browser_flow(dataset: dict[str, object], token: str, profile: dict[str, object]) -> dict[str, object]:
    console_events: list[str] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1200})
        page.on(
            "console",
            lambda msg: console_events.append(f"[{msg.type.upper()}] {msg.text}"),
        )
        page.add_init_script(
            """
            ({ token, profile }) => {
              localStorage.setItem('auth_token', token);
              localStorage.setItem('auth_profile', JSON.stringify(profile));
              localStorage.setItem('user', JSON.stringify(profile));
              localStorage.setItem('theme', 'light');
              localStorage.setItem('colorScheme', 'light');
              localStorage.setItem('app_language', 'ru');
              localStorage.setItem('language', 'ru');
              localStorage.setItem('ui_theme', 'light');
              localStorage.setItem('ui.accent', 'blue');
            }
            """,
            {"token": token, "profile": profile},
        )

        page.goto(f"{WEB_BASE}/doctor-panel", wait_until="domcontentloaded")
        page.wait_for_load_state("networkidle")

        queue_tab = page.get_by_role("button", name=re.compile("Очередь"))
        queue_tab.click()

        patient_locator = page.get_by_text(str(dataset["patient_name"]), exact=False)
        patient_locator.wait_for(timeout=20000)
        status_before = page.get_by_text("Ожидает", exact=False).first.inner_text()
        page.screenshot(path=str(BEFORE_SCREENSHOT), full_page=True)

        call_button = page.get_by_role("button", name=re.compile("Вызвать следующего"))
        call_button.click()

        try:
            page.get_by_text("Вызван", exact=False).first.wait_for(timeout=20000)
        except PlaywrightTimeoutError as exc:
            page.screenshot(path=str(AFTER_SCREENSHOT), full_page=True)
            browser.close()
            raise RuntimeError("UI did not transition to called state") from exc

        page.screenshot(path=str(AFTER_SCREENSHOT), full_page=True)
        url_after = page.url
        browser.close()

    return {
        "status_before_ui": status_before,
        "url_after": url_after,
        "console_events": console_events[-20:],
    }


def main() -> None:
    wait_for_http(f"{API_BASE}/api/v1/health")
    wait_for_http(WEB_BASE)

    dataset = ensure_general_queue_dataset()
    token, profile = login_doctor()
    queue_before = fetch_queue_state(token)
    browser_result = run_browser_flow(dataset, token, profile)
    queue_after = fetch_queue_state(token)

    matched_entry = next(
        (
            entry
            for entry in queue_after.get("entries", [])
            if entry.get("id") == dataset["entry_id"]
        ),
        None,
    )
    if not matched_entry:
        raise RuntimeError(
            f"Entry {dataset['entry_id']} disappeared from general queue payload"
        )

    result = {
        "api_base": API_BASE,
        "web_base": WEB_BASE,
        "dataset": dataset,
        "queue_before_stats": queue_before.get("stats"),
        "queue_after_stats": queue_after.get("stats"),
        "matched_entry_after": matched_entry,
        "browser": browser_result,
        "artifacts": {
            "before": str(BEFORE_SCREENSHOT),
            "after": str(AFTER_SCREENSHOT),
            "json": str(RESULT_JSON),
        },
    }
    write_result(result)

    if matched_entry.get("status") != "called":
        raise RuntimeError(
            f"DOC-02 expected called status, got {matched_entry.get('status')}"
        )

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
