from __future__ import annotations

import sys
from typing import List, Dict

import requests


BASE_URL = "http://127.0.0.1:8003/api/v1"

# Критические системные пользователи, которых нельзя трогать
CRITICAL_USERNAMES = {
    "admin",
    "registrar",
    "doctor",
    "lab",
    "cashier",
    "cardio",
    "derma",
    "dentist",
}


def login_admin(username: str = "admin", password: str = "admin123") -> str:
    resp = requests.post(
        f"{BASE_URL}/authentication/login",
        json={"username": username, "password": password},
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    print(f"LOGIN_RESPONSE: {data}")
    token = data.get("access_token")
    if not token:
        raise RuntimeError(f"No access_token in login response: {data}")
    return token


def fetch_all_users(token: str) -> List[Dict]:
    headers = {"Authorization": f"Bearer {token}"}
    users: List[Dict] = []
    page = 1
    while True:
        r = requests.get(
            f"{BASE_URL}/users/users",
            params={"page": page, "per_page": 100},
            headers=headers,
            timeout=20,
        )
        r.raise_for_status()
        payload = r.json()
        users.extend(payload.get("users", []))
        total_pages = int(payload.get("total_pages", 1))
        if page >= total_pages:
            break
        page += 1
    return users


def select_non_example_ids(users: List[Dict]) -> List[int]:
    ids: List[int] = []
    for u in users:
        username = (u.get("username") or "").strip()
        email = (u.get("email") or "").strip()
        if username in CRITICAL_USERNAMES:
            continue
        if email.endswith("@example.com"):
            continue
        uid = u.get("id")
        if isinstance(uid, int):
            ids.append(uid)
    return ids


def bulk_action(token: str, user_ids: List[int], action: str) -> Dict:
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    body = {"action": action, "user_ids": user_ids}
    print(f"BULK_ACTION: URL={BASE_URL}/users/users/bulk-action")
    print(f"BULK_ACTION: headers={headers}")
    print(f"BULK_ACTION: body={body}")
    r = requests.post(
        f"{BASE_URL}/users/users/bulk-action",
        json=body,
        headers=headers,
        timeout=60,
    )
    print(f"BULK_ACTION: status={r.status_code}, response={r.text}")
    if r.status_code >= 400:
        # Вернем текст для диагностики
        return {"success": False, "status": r.status_code, "text": r.text}
    try:
        return r.json()
    except Exception:
        return {"success": True, "status": r.status_code, "text": r.text}


def check_profile(token: str) -> int:
    headers = {"Authorization": f"Bearer {token}"}
    r = requests.get(f"{BASE_URL}/authentication/profile", headers=headers, timeout=15)
    return r.status_code


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in {"deactivate", "delete"}:
        print("Usage: python backend/scripts/cleanup_non_example_users.py [deactivate|delete]")
        sys.exit(2)

    action = sys.argv[1]
    token = login_admin()
    users = fetch_all_users(token)
    ids = select_non_example_ids(users)
    print(f"TOTAL_USERS={len(users)} TARGET_IDS={len(ids)}")
    if not ids:
        print("Nothing to process")
        return

    result = bulk_action(token, ids, action)
    print(f"BULK_{action.upper()} RESULT=", result)

    status = check_profile(token)
    print(f"PROFILE_STATUS={status}")


if __name__ == "__main__":
    main()


