# 2026-03-27 CASH-02 online autoconfirm

## Summary
- Local cashier online smoke now auto-confirms payment intents in dev smoke mode so `CASH-02` can complete without a real provider redirect.

## Root cause
- The cashier online widget treated init success as a terminal payment state and used the wrong confirm endpoint for the current backend router shape.
- Backend payment status also returned `paid`, while the UI only treated `completed` as success.

## Fix
- `PaymentWidget` now:
  - detects local smoke mode
  - posts confirm requests to `/api/v1/cashier/payments/{payment_id}/confirm`
  - normalizes backend statuses so `paid` maps to `completed`
- `PaymentSuccess` now:
  - treats `paid` as a success state for the rendered UI

## Verification
- Browser smoke on `/cashier-panel` auto-confirmed payment `196`
- Pending cashier list dropped to `0`
- Live screenshot captured at `output/playwright/cash-02-local-smoke-final.png`
