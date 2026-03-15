# Wave 2C OnlineDay Main Track Separation

Date: 2026-03-09
Mode: analysis-first, docs-only

## Question

Do migrated main-track queue families still depend on OnlineDay?

## Checked families

- confirmation family
- registrar batch-only family
- wizard family
- QR full-update family

## Checked files

- `backend/app/services/visit_confirmation_service.py`
- `backend/app/api/v1/endpoints/registrar_integration.py`
- `backend/app/services/registrar_wizard_queue_assignment_service.py`
- `backend/app/services/qr_full_update_queue_assignment_service.py`
- `backend/app/services/queue_domain_service.py`
- `backend/app/services/queue_service.py`

## Result

`any active dependency remains? no`

No active dependency was found on:

- `OnlineDay`
- `app.services.online_queue`
- `app.models.online`
- `last_ticket`

inside the migrated main allocator families.

## Interpretation

The main queue track is now separated from OnlineDay.

OnlineDay remains a side track because of its own mounted legacy surface, not
because any migrated SSOT family still needs it.
