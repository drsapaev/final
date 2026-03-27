from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from pathlib import Path

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


ROOT = Path(r"c:\final\output\playwright")
ROOT.mkdir(parents=True, exist_ok=True)

FRONTEND_URL = "http://127.0.0.1:4174"
BACKEND_URL = "http://127.0.0.1:18002"
LOGIN_URL = f"{BACKEND_URL}/api/v1/authentication/login"
DERMA_URL = f"{FRONTEND_URL}/dermatologist?tab=appointments"


def login() -> dict:
    payload = json.dumps(
        {"username": "derma@example.com", "password": "derma123"}
    ).encode("utf-8")
    request = urllib.request.Request(
        LOGIN_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def wait_for_json(url: str, token: str, timeout: float = 20.0) -> list[dict]:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            request = urllib.request.Request(
                url,
                headers={"Authorization": f"Bearer {token}"},
                method="GET",
            )
            with urllib.request.urlopen(request, timeout=10) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.URLError:
            time.sleep(0.5)
    raise TimeoutError(f"Timed out waiting for JSON from {url}")


def save_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    auth = login()
    token = auth["access_token"]
    user = auth["user"]

    tracked_responses: list[dict] = []
    verification: dict[str, object] = {
        "frontend_url": FRONTEND_URL,
        "backend_url": BACKEND_URL,
        "user": user,
        "saved_exam_id": None,
        "patient_id": None,
        "visit_id": None,
    }

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1400})

        def on_response(response) -> None:
            url = response.url
            if "/api/v1/derma/" in url:
                tracked_responses.append(
                    {
                        "url": url,
                        "status": response.status,
                        "method": response.request.method,
                    }
                )

        page.on("response", on_response)

        page.goto(f"{FRONTEND_URL}/login", wait_until="domcontentloaded")
        page.evaluate(
            """({ token, user }) => {
                window.localStorage.setItem('auth_token', token);
                window.localStorage.setItem('access_token', token);
                window.localStorage.setItem('user', JSON.stringify(user));
                window.localStorage.setItem('auth_profile', JSON.stringify(user));
                window.localStorage.setItem('theme', 'light');
                window.localStorage.setItem('language', 'ru');
            }""",
            {"token": token, "user": user},
        )

        page.goto(DERMA_URL, wait_until="domcontentloaded")
        page.get_by_role("heading", name="Записи к дерматологу").wait_for(timeout=20000)
        page.screenshot(path=str(ROOT / "derma-live-appointments.png"), full_page=True)

        row = page.locator("tr", has_text="Админ Пациент Поток").first
        row.click()
        page.get_by_role("heading", name="Прием пациента: Админ Пациент Поток").wait_for(
            timeout=20000
        )
        page.screenshot(path=str(ROOT / "derma-live-visit.png"), full_page=True)

        page.get_by_role("button", name="Skin Examination").click()
        page.get_by_role("heading", name="Осмотры кожи").wait_for(timeout=10000)

        page.get_by_role("button", name="Новый осмотр").click()
        page.locator('input[type="date"]').fill("2026-03-21")
        page.get_by_role("combobox").select_option("combination")
        page.get_by_role(
            "textbox",
            name="Хорошее, удовлетворительное, проблемное",
        ).fill("Умеренная сухость и чувствительность")
        page.get_by_role("textbox", name="Акне, пигментация, родинки").fill(
            "Локальная эритема на щеках"
        )
        page.get_by_role("textbox", name="Диагноз").fill(
            "Чувствительная комбинированная кожа"
        )
        page.get_by_role("textbox", name="План лечения и рекомендации").fill(
            "Мягкий уход, SPF, контроль через 2 недели"
        )

        with page.expect_response(
            lambda response: response.request.method == "POST"
            and response.url.endswith("/api/v1/derma/examinations"),
            timeout=20000,
        ) as save_response_info:
            page.get_by_role("button", name="Сохранить осмотр").click()

        save_response = save_response_info.value
        saved_payload = save_response.json()
        verification["saved_exam_id"] = saved_payload.get("id")
        verification["patient_id"] = saved_payload.get("patient_id")
        verification["visit_id"] = saved_payload.get("visit_id")
        verification["save_status"] = save_response.status
        verification["save_payload"] = saved_payload

        page.get_by_text("Осмотр кожи сохранен успешно").wait_for(timeout=10000)
        page.get_by_text("Чувствительная комбинированная кожа").wait_for(timeout=10000)
        page.screenshot(path=str(ROOT / "derma-live-skin-after-save.png"), full_page=True)

        page.get_by_role("button", name="History").click()
        page.get_by_role("heading", name="История приемов и процедур").wait_for(
            timeout=10000
        )
        page.get_by_text("Чувствительная комбинированная кожа").wait_for(timeout=10000)
        page.screenshot(path=str(ROOT / "derma-live-history-after-save.png"), full_page=True)

        page.get_by_role("button", name="Skin Examination").click()
        page.get_by_text("Чувствительная комбинированная кожа").wait_for(timeout=10000)
        page.screenshot(path=str(ROOT / "derma-live-skin-reopen.png"), full_page=True)

        browser.close()

    patient_id = verification["patient_id"]
    if not patient_id:
        raise RuntimeError("Saved examination did not return patient_id")

    api_data = wait_for_json(
        f"{BACKEND_URL}/api/v1/derma/examinations?patient_id={patient_id}&limit=10",
        token=token,
    )
    verification["api_exam_count"] = len(api_data)
    verification["api_latest_exam_id"] = api_data[0]["id"] if api_data else None
    verification["tracked_responses"] = tracked_responses

    save_json(ROOT / "derma-live-verification.json", verification)
    print(json.dumps(verification, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
