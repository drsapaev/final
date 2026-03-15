"""
Direct/manual smoke test of cart creation endpoint.

Note:
- this file is intentionally executable as a standalone script;
- it is kept import-safe so pytest discovery does not execute network/login side effects.
"""

from __future__ import annotations

import json
import sys

import requests

sys.path.insert(0, ".")


API_BASE = "http://localhost:8000"


def main() -> int:
    auth_token = "your_token_here"

    # First, login as registrar
    print("[*] Logging in as registrar...")
    login_response = requests.post(
        f"{API_BASE}/api/v1/auth/minimal-login",
        json={"username": "registrar", "password": "registrar123"},
    )

    if login_response.status_code == 200:
        login_data = login_response.json()
        if "access_token" in login_data:
            auth_token = login_data["access_token"]
            print("[OK] Logged in successfully")
        else:
            print(f"[ERROR] No access_token in response: {login_data}")
            return 1
    else:
        print(f"[ERROR] Login failed: {login_response.status_code}")
        print(f"Response: {login_response.text}")
        return 1

    # Now try to create a cart
    print("\n[*] Testing cart creation...")

    # Get a patient to use
    patients_response = requests.get(
        f"{API_BASE}/api/v1/patients/",
        headers={"Authorization": f"Bearer {auth_token}"},
    )

    if patients_response.status_code != 200:
        print(f"[ERROR] Failed to get patients: {patients_response.status_code}")
        return 1

    patients = patients_response.json()
    if not patients:
        print("[ERROR] No patients found")
        return 1

    patient_id = patients[0]["id"]
    print(f"[OK] Using patient ID: {patient_id}")

    # Get a service to use
    services_response = requests.get(
        f"{API_BASE}/api/v1/registrar/services",
        headers={"Authorization": f"Bearer {auth_token}"},
    )

    if services_response.status_code != 200:
        print(f"[ERROR] Failed to get services: {services_response.status_code}")
        return 1

    services = services_response.json()
    print(f"[DEBUG] Services response type: {type(services)}")
    print(f"[DEBUG] Services response: {services}")

    # Handle different response formats
    if isinstance(services, dict):
        if "data" in services:
            services_list = services["data"]
        elif "services" in services:
            services_list = services["services"]
        elif "services_by_group" in services:
            # Flatten services from all groups
            services_list = []
            for group_services in services["services_by_group"].values():
                services_list.extend(group_services)
        else:
            services_list = list(services.values())[0] if services else []
    else:
        services_list = services

    if not services_list:
        print("[ERROR] No services found")
        return 1

    service_id = services_list[0]["id"]
    print(f"[OK] Using service ID: {service_id} ({services_list[0]['name']})")

    # Create cart request
    cart_request = {
        "patient_id": patient_id,
        "discount_mode": "none",
        "payment_method": "cash",
        "notes": "Test cart creation",
        "visits": [
            {
                "department": "general",
                "visit_date": "2025-11-26",
                "visit_time": "10:00",
                "doctor_id": None,
                "services": [
                    {"service_id": service_id, "quantity": 1, "custom_price": None}
                ],
                "notes": "Test visit",
            }
        ],
    }

    print("\n[*] Sending cart request...")
    print(json.dumps(cart_request, indent=2, ensure_ascii=False))

    cart_response = requests.post(
        f"{API_BASE}/api/v1/registrar/cart",
        headers={
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json",
        },
        json=cart_request,
    )

    print(f"\n[*] Response status: {cart_response.status_code}")
    print(f"[*] Response headers: {dict(cart_response.headers)}")
    print("\n[*] Response body:")
    try:
        response_json = cart_response.json()
        print(json.dumps(response_json, indent=2, ensure_ascii=False))
    except Exception:
        print(cart_response.text)

    if cart_response.status_code != 200:
        print(f"\n[ERROR] Cart creation failed with status {cart_response.status_code}")
        return 1

    print("\n[OK] Cart created successfully!")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
