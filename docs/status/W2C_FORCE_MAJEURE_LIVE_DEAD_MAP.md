# Wave 2C Force Majeure Live vs Dead Map

Date: 2026-03-09
Mode: analysis-first, docs-only

| File | Function / endpoint | Category | Why still live or not | Cleanup-later candidate |
|---|---|---|---|---|
| `backend/app/api/v1/endpoints/force_majeure.py` | `transfer_queue_to_tomorrow()` | `LIVE_MOUNTED_EXCEPTIONAL` | Mounted production transfer endpoint | No |
| `backend/app/api/v1/endpoints/force_majeure.py` | `cancel_queue_with_refund()` | `LIVE_MOUNTED_EXCEPTIONAL` | Mounted production cancel/refund endpoint | No |
| `backend/app/api/v1/endpoints/force_majeure.py` | `get_pending_entries_for_force_majeure()` | `LIVE_MOUNTED_EXCEPTIONAL` | Mounted production selection/read endpoint for exceptional flow | No |
| `backend/app/api/v1/endpoints/force_majeure.py` | refund-request and deposit endpoints | `LIVE_MOUNTED_EXCEPTIONAL` | Mounted operational follow-up surface for the same exceptional domain | No |
| `backend/app/services/force_majeure_service.py` | transfer / cancel / refund / deposit methods | `LIVE_MOUNTED_EXCEPTIONAL` | Runtime owner of force_majeure semantics | No |
| `backend/app/services/force_majeure_api_service.py` | API service wrapper | `EXCEPTIONAL_SUPPORT_ONLY` | Mounted endpoints delegate through it, but it does not own policy by itself | No |
| `backend/app/repositories/force_majeure_api_repository.py` | repository helper | `EXCEPTIONAL_SUPPORT_ONLY` | Persistence helper for mounted API/service layer | No |
| `backend/app/services/force_majeure_service.py` | `_get_next_queue_number()` | `EXCEPTIONAL_SUPPORT_ONLY` | Internal helper, live only through transfer flow | No |

## Dead or disabled surface

No dead or disabled force_majeure module was identified in the current runtime.

## Map verdict

Unlike OnlineDay, force_majeure is not surrounded by much dead legacy surface.
It is a compact live exceptional-domain with a small support layer around it.
