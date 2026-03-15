# Wave 2C Force Majeure Inventory

Date: 2026-03-09
Mode: characterization-first

| File | Function | Mounted | Production relevant | Allocator behavior type | Numbering affected | Duplicate policy affected | Queue time / fairness affected | Visit linkage affected | Risk level |
|---|---|---:|---:|---|---:|---:|---:|---:|---|
| `backend/app/api/v1/endpoints/force_majeure.py` | `transfer_queue_to_tomorrow()` | yes | yes | Mounted transfer entry point | yes | yes | yes | yes | High |
| `backend/app/api/v1/endpoints/force_majeure.py` | `cancel_queue_with_refund()` | yes | yes | Mounted exceptional cancel/refund flow | no | yes | yes | yes | High |
| `backend/app/api/v1/endpoints/force_majeure.py` | `get_pending_entries_for_force_majeure()` | yes | yes | Read-model selector for eligible rows | no | yes | no | no | Medium |
| `backend/app/services/force_majeure_api_service.py` | `transfer_queue_to_tomorrow()` | no | yes | API orchestration into domain transfer service | yes | yes | yes | yes | High |
| `backend/app/services/force_majeure_api_service.py` | `cancel_queue_with_refund()` | no | yes | API orchestration into cancel/refund domain flow | no | yes | yes | yes | High |
| `backend/app/services/force_majeure_service.py` | `get_pending_entries()` | no | yes | Eligibility selector for force-majeure operations | no | yes | yes | no | High |
| `backend/app/services/force_majeure_service.py` | `transfer_entries_to_tomorrow()` | no | yes | Exceptional transfer allocator | yes | yes | yes | yes | Critical |
| `backend/app/services/force_majeure_service.py` | `cancel_entries_with_refund()` | no | yes | Exceptional cancel plus refund/deposit orchestration | no | yes | yes | yes | Critical |
| `backend/app/services/force_majeure_service.py` | `_get_or_create_queue()` | no | yes | Tomorrow-queue resolution / creation helper | indirectly | no | no | no | Medium |
| `backend/app/services/force_majeure_service.py` | `_get_next_queue_number()` | no | yes | Legacy-style next-number allocator | yes | no | indirectly | no | Critical |
| `backend/app/services/force_majeure_service.py` | `_get_payment_for_entry()` / `_add_to_deposit()` / `_create_refund_request()` | no | yes | Payment/refund side-effects for exceptional cancel flow | no | no | no | yes | High |

## Key Runtime Notes

- The only allocator-creating path is `transfer_entries_to_tomorrow()`.
- Transfer is mounted and production-relevant through `/api/v1/force-majeure/transfer`.
- Cancellation is production-relevant but does not allocate a new queue row; it
  is coupled to refund/deposit handling.
- The family is not a normal join/create caller. It is an exceptional queue
  transfer/cancel domain.
