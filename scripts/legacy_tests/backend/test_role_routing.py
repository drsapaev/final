"""
Manual smoke checks for role routing and specialist API access.

The script reads QA_* credential environment variables, but it must never print
passwords, bearer tokens, response bodies, or raw exception objects.
"""

import os
import sys

import requests

BASE_URL = "http://127.0.0.1:18000"
REQUEST_TIMEOUT_SECONDS = 10

ROLE_CHECKS = [
    (None, "QA_ADMIN_USERNAME", "QA_ADMIN_PASSWORD", "Admin"),
    ("registrar", None, "QA_REGISTRAR_PASSWORD", "Registrar"),
    ("lab", None, "QA_LAB_PASSWORD", "Lab"),
    ("doctor", None, "QA_DOCTOR_PASSWORD", "Doctor"),
    ("cashier", None, "QA_CASHIER_PASSWORD", "Cashier"),
    ("cardio", None, "QA_CARDIO_PASSWORD", "cardio"),
    ("derma", None, "QA_DERMA_PASSWORD", "derma"),
    ("dentist", None, "QA_DENTIST_PASSWORD", "dentist"),
]


def _env_present(name):
    return bool(os.getenv(name))


def load_role_checks():
    role_checks = []
    missing_required_env = False

    for (
        default_username,
        username_env_name,
        password_env_name,
        expected_role,
    ) in ROLE_CHECKS:
        username = os.getenv(username_env_name) if username_env_name else default_username
        if username and _env_present(password_env_name):
            role_checks.append((username, password_env_name, expected_role))
        else:
            missing_required_env = True

    if missing_required_env:
        print(
            "ERROR: set all required QA role credential env vars before "
            "running this manual smoke.",
            file=sys.stderr,
        )
        return None

    return role_checks


def load_admin_username():
    if not os.getenv("QA_ADMIN_USERNAME") or not _env_present("QA_ADMIN_PASSWORD"):
        print(
            "ERROR: set required QA admin credential env vars before "
            "running admin API access smoke.",
            file=sys.stderr,
        )
        return None
    return os.environ["QA_ADMIN_USERNAME"]


def fetch_authenticated_profile(username, password_env_name):
    login_url = f"{BASE_URL}/api/v1/authentication/login"
    login_data = {
        "username": username,
        "password": os.environ[password_env_name],
    }

    result = {
        "login_status": None,
        "token_keys": [],
        "profile_status": None,
        "actual_role": None,
        "error_type": None,
    }

    try:
        response = requests.post(
            login_url,
            json=login_data,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        result["login_status"] = response.status_code
        if response.status_code != 200:
            return result

        token_data = response.json()
        result["token_keys"] = list(token_data.keys())

        token = token_data.get("access_token")
        if not token and token_data.get("tokens"):
            token = token_data["tokens"].get("access_token")
        if not token:
            return result

        profile_response = requests.get(
            f"{BASE_URL}/api/v1/authentication/profile",
            headers={"Authorization": f"Bearer {token}"},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        result["profile_status"] = profile_response.status_code
        if profile_response.status_code != 200:
            return result

        profile = profile_response.json()
        result["actual_role"] = profile.get("role")
        return result
    except Exception as exc:
        result["error_type"] = type(exc).__name__
        return result


def probe_admin_endpoints(admin_username):
    login_data = {
        "username": admin_username,
        "password": os.environ["QA_ADMIN_PASSWORD"],
        "grant_type": "password",
    }
    result = {"login_status": None, "probes": None, "error_type": None}

    try:
        response = requests.post(
            f"{BASE_URL}/api/v1/authentication/login",
            json=login_data,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        result["login_status"] = response.status_code
        if response.status_code != 200:
            return result

        token = response.json().get("access_token")
        if not token:
            return result

        headers = {"Authorization": f"Bearer {token}"}
        endpoints = [
            ("/api/v1/cardio/ecg", "Cardio API"),
            ("/api/v1/derma/examinations", "Derma API"),
            ("/api/v1/dental/examinations", "Dental API"),
            ("/api/v1/lab/tests", "Lab API"),
        ]

        probes = []
        for endpoint, name in endpoints:
            try:
                endpoint_response = requests.get(
                    f"{BASE_URL}{endpoint}",
                    headers=headers,
                    timeout=REQUEST_TIMEOUT_SECONDS,
                )
                probes.append(
                    {
                        "name": name,
                        "status_code": endpoint_response.status_code,
                        "error_type": None,
                    }
                )
            except Exception as exc:
                probes.append(
                    {
                        "name": name,
                        "status_code": None,
                        "error_type": type(exc).__name__,
                    }
                )

        result["probes"] = probes
        return result
    except Exception as exc:
        result["error_type"] = type(exc).__name__
        return result


def test_user_login_and_role(username, password_env_name, expected_role):
    print(f"Testing role: {expected_role}")

    auth_result = fetch_authenticated_profile(username, password_env_name)
    if auth_result["error_type"]:
        print(f"ERROR: role smoke failed with {auth_result['error_type']}")
        return False

    print(f"DEBUG: Login response status: {auth_result['login_status']}")
    if auth_result["login_status"] != 200:
        print(f"ERROR: login failed: {auth_result['login_status']}")
        print("DEBUG: Login response body is not printed")
        return False

    print(f"DEBUG: Token data keys: {auth_result['token_keys']}")
    if not auth_result["profile_status"]:
        print("ERROR: access token was not received")
        print("DEBUG: Token response values are not printed")
        return False

    print(f"DEBUG: Profile response status: {auth_result['profile_status']}")
    if auth_result["profile_status"] != 200:
        print(f"ERROR: profile was not received: {auth_result['profile_status']}")
        print("DEBUG: Profile response body is not printed")
        return False

    actual_role = auth_result["actual_role"]
    if actual_role != expected_role:
        print(f"ERROR: wrong role: expected {expected_role}, got {actual_role}")
        return False

    print(f"OK: role {actual_role} is correct")
    return True


def test_all_critical_users():
    print("Testing role routing and authentication")
    print("=" * 60)

    critical_users = load_role_checks()
    if critical_users is None:
        return False

    results = []
    for username, password_env_name, expected_role in critical_users:
        result = test_user_login_and_role(username, password_env_name, expected_role)
        results.append((expected_role, result))
        print()

    print("TEST RESULTS:")
    print("=" * 60)
    passed = sum(1 for _, result in results if result)
    total = len(results)

    for expected_role, result in results:
        status = "PASS" if result else "FAIL"
        print(f"{status} {expected_role}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("SUCCESS: all role-routing tests passed.")
        return True

    print("WARNING: role-routing problems were detected.")
    return False


def test_api_endpoints_access():
    print("\nTesting specialist API endpoint access")
    print("=" * 60)

    admin_username = load_admin_username()
    if not admin_username:
        return False

    admin_probe = probe_admin_endpoints(admin_username)
    if admin_probe["error_type"]:
        print(f"ERROR: admin endpoint smoke failed with {admin_probe['error_type']}")
        return False
    if admin_probe["login_status"] != 200 or admin_probe["probes"] is None:
        print("ERROR: failed to get admin token")
        return False

    for probe in admin_probe["probes"]:
        name = probe["name"]
        if probe["error_type"]:
            print(f"ERROR: {name}: exception {probe['error_type']}")
        elif probe["status_code"] in [200, 404]:
            print(f"OK: {name}: accessible")
        else:
            print(f"ERROR: {name}: status {probe['status_code']}")

    return True


if __name__ == "__main__":
    print("Starting role-routing smoke checks")
    print("=" * 60)

    try:
        response = requests.get(
            f"{BASE_URL}/api/v1/health",
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        if response.status_code != 200:
            print("ERROR: backend server is unavailable")
            sys.exit(1)
    except Exception:
        print("ERROR: backend server is unavailable")
        sys.exit(1)

    success1 = test_all_critical_users()
    success2 = test_api_endpoints_access()

    if success1 and success2:
        print("\nSUCCESS: all smoke checks passed.")
        sys.exit(0)

    print("\nWARNING: smoke checks detected problems.")
    sys.exit(1)
