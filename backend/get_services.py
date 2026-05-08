#!/usr/bin/env python3
"""Env-driven services API smoke helper."""

from __future__ import annotations

import os

import requests


def _required_services_smoke_token() -> str:
    token = os.getenv("SERVICES_SMOKE_TOKEN", "").strip()
    if not token:
        raise SystemExit("Set SERVICES_SMOKE_TOKEN before running get_services.py.")
    return token


def _api_base_url() -> str:
    return os.getenv("SERVICES_SMOKE_API_BASE_URL", "http://127.0.0.1:18000").rstrip("/")


def main() -> int:
    token = _required_services_smoke_token()
    response = requests.get(
        f"{_api_base_url()}/api/v1/services",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )

    if response.status_code != 200:
        print(
            "Failed to fetch services: "
            f"{response.status_code} - {response.text[:500]}"
        )
        return 1

    services = response.json()
    print(f"Total services: {len(services)}")
    for index, service in enumerate(services[:10], start=1):
        print(
            f"{index}. ID: {service.get('id')}, "
            f"Code: {service.get('code')}, Name: {service.get('name')}"
        )

    k01_service = next((item for item in services if item.get("code") == "K01"), None)
    if k01_service:
        print(f"K01 service id: {k01_service['id']}")
    else:
        print("K01 service was not found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
