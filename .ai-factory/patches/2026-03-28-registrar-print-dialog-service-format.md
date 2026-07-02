# Registrar Print Dialog Service Formatting

## Root Cause

`PrintDialog` was receiving appointment `services` values that were not guaranteed to be plain strings. In the live registrar flow, the first service could be object-shaped, which rendered as `[object Object]` in the ticket preview.

## Fix

- Added robust label formatting in `frontend/src/components/dialogs/PrintDialog.jsx`.
- Normalized string/number/object service values to readable labels before joining them for display.
- Kept the print flow behavior unchanged: print still closes the dialog after the document is sent.

## Verification

- Live browser smoke on `registrar-panel?tab=appointments`.
- The print dialog now renders readable services text:
  - `Консультация дерматолога-косметолога, D01`
- After `Печать`, the dialog closes successfully.
- Evidence captured in:
  - `output/playwright/reg-06-print-smoke-final.png`

