# W2D visit_confirmation_api_service cleanup

## What changed

Removed:

- `backend/app/services/visit_confirmation_api_service.py`

## Why this was safe

The file was a duplicate router-like compatibility artifact rather than a live
runtime owner.

Mounted confirmation behavior already runs through:

- `backend/app/api/v1/endpoints/visit_confirmation.py`
- `backend/app/services/visit_confirmation_service.py`

No confirmed in-repo live import or test dependency on the duplicate file was
found before removal.

## What did not change

This slice did not change:

- confirmation endpoint registration
- confirmation service behavior
- queue assignment or confirmation-domain semantics
- any confirmation contract shape

## Practical effect

This removes one more stale support-only artifact and reduces duplicate
confirmation surface area without touching mounted runtime behavior.
