# W2D appointments.qrcode deprecation prep status

Date: 2026-03-11
Mode: bounded implementation

## Result

`COMPLETE`

## Outcome

`GET /api/v1/appointments/qrcode` now:

- remains mounted
- remains behaviorally unchanged
- is explicitly deprecated in OpenAPI
- has an explicit response model for contract clarity

## Verification

- `pytest tests/test_openapi_contract.py -q`

## Follow-up implication

The route is now in the same deprecation-prep category as other legacy
compatibility surfaces that were intentionally kept mounted for safety.
