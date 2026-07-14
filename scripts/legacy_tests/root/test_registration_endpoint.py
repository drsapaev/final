import os
import sys

import requests


TOKEN_ENV = "REGISTRAR_API_TOKEN"
CART_URL = "http://localhost:18000/api/v1/registrar/cart"
TODAY_QUEUES_URL = "http://localhost:18000/api/v1/registrar/queues/today"


TEST_DATA = {
    "patient_id": 1,
    "visits": [
        {
            "doctor_id": None,
            "services": [
                {
                    "service_id": 1,
                    "quantity": 1,
                }
            ],
            "visit_date": "2025-10-01",
            "visit_time": "14:00",
            "department": "cardiology",
            "notes": None,
        }
    ],
    "discount_mode": "none",
    "payment_method": "cash",
    "all_free": False,
    "notes": None,
}


def _auth_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def main() -> int:
    token = os.environ.get(TOKEN_ENV, "").strip()
    if not token:
        print(f"Set {TOKEN_ENV} to a locally generated bearer token before running this smoke script.")
        return 2

    try:
        response = requests.post(
            CART_URL,
            headers=_auth_headers(token),
            json=TEST_DATA,
            timeout=10,
        )
    except requests.RequestException as exc:
        print(f"Cart request failed: {exc}")
        return 1

    print(f"Cart response: {response.status_code}")
    if response.status_code != 200:
        print(response.text)
        return 1

    data = response.json()
    print(f"Visit IDs: {data.get('visit_ids', [])}")
    print(f"Invoice ID: {data.get('invoice_id')}")
    print(f"Total amount: {data.get('total_amount')}")

    try:
        queues_response = requests.get(
            TODAY_QUEUES_URL,
            headers=_auth_headers(token),
            timeout=5,
        )
    except requests.RequestException as exc:
        print(f"Queue verification request failed: {exc}")
        return 1

    print(f"Queues response: {queues_response.status_code}")
    if queues_response.status_code != 200:
        print(queues_response.text)
        return 1

    queues_data = queues_response.json()
    queues = queues_data.get("queues", [])
    total_entries = sum(len(queue.get("entries", [])) for queue in queues)
    print(f"Queues: {len(queues)}")
    print(f"Total entries: {total_entries}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
