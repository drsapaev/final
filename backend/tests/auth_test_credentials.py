from __future__ import annotations

from hashlib import sha256


def _credential(label: str) -> str:
    digest = sha256(f"clinic-test-auth:{label}".encode("utf-8")).hexdigest()
    return f"qa-{label}-{digest[:20]}-A1!"


ADMIN_PASSWORD = _credential("admin")
CARDIO_PASSWORD = _credential("cardio")
CASHIER_PASSWORD = _credential("cashier")
DENTIST_PASSWORD = _credential("dentist")
DOCTOR_PASSWORD = _credential("doctor")
DUMMY_PASSWORD_HASH = "qa-test-hash-placeholder"
GENERIC_TEST_PASSWORD = _credential("generic")
PATIENT_PASSWORD = _credential("patient")
REGISTRAR_PASSWORD = _credential("registrar")
