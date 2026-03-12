# Wave 2C Force Majeure Main Track Separation

Date: 2026-03-09
Mode: analysis-first, docs-only

## Question

Do migrated main-track queue families depend on force_majeure semantics?

## Checked families

- confirmation family
- registrar batch-only family
- wizard family
- QR family

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

- `force_majeure`
- `ForceMajeureService`
- `ForceMajeureApiService`
- force_majeure-specific transfer semantics

inside the migrated main allocator families.

## Interpretation

The main queue track is fully separated from force_majeure.

Force majeure remains a side track because of its own exceptional-domain
behavior, not because SSOT queue families still depend on it.
