# 2026-03-27 - Billing timezone normalization

## What changed
- `BillingService` now normalizes timezone-aware timestamps to local-naive `datetime` values before persisting or comparing invoice/payment/reminder dates.
- `create_payment_reminders()`, `send_due_reminders()`, and `create_recurring_invoices()` now compare like-with-like instead of mixing aware and naive datetimes.
- Added a targeted regression test for the create-invoice + reminder path with an aware `queue_service` clock.

## Verification
- `python -m pytest tests/unit/test_billing_service_timezone.py -q` -> `1 passed`
- `python -m py_compile app/services/billing_service.py tests/unit/test_billing_service_timezone.py`
- Live browser smoke on `/admin/settings?section=billing` created `INV-2026-000002` and returned to the invoice list without the timezone error.

## Evidence
- `.playwright-cli/page-2026-03-27T08-00-52-463Z.yml`
- `.playwright-cli/network-2026-03-27T08-01-29-244Z.log`
