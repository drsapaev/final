# W2D appointments.qrcode deprecation prep plan

Date: 2026-03-11
Mode: bounded implementation

## In scope

- `backend/app/api/v1/endpoints/appointments.py`
- `backend/tests/test_openapi_contract.py`
- narrow status/architecture docs for this slice

## Exact change

Mark `GET /api/v1/appointments/qrcode` as deprecated in OpenAPI and give it an
explicit response model without changing payload behavior.

## Why this is safe

The route was already verified as:

- mounted
- read-only
- support-only
- lacking a confirmed in-repo live consumer

So deprecation-prep is safer than immediate removal and more useful than
leaving it as an unlabeled stub surface.

## Out of scope

- route removal
- redirecting QR consumers
- changing payload format
- touching `open_day`, `close_day`, `next_ticket`, or queue stats
