# Wave 2A Service/Repository Slices

Date: 2026-03-06  
Track: W2A (Service/Repository Completion)  
Execution rule: low-risk non-protected first.

## Slice Backlog

| ID | Target files | Why this slice is safe | Expected refactor shape | Tests to run | Expected artifacts | Human review required | Current status |
|---|---|---|---|---|---|---|---|
| `W2A-SR-001` | `backend/app/api/v1/endpoints/messages.py` | Non-protected module; existing `MessagesApiService` + `MessagesApiRepository` already implemented | Router endpoints become thin and call service methods (`/send`, `/conversations`, `/conversation/{user_id}`, `/unread`, `/{message_id}/read`, `/{message_id}`) | `cd backend && pytest -q` | `docs/status/wave2a/W2A-SR-001_STATUS.md` | No | `done` |
| `W2A-SR-002` | `backend/app/api/v1/endpoints/messages.py` | Same module and architecture pattern; bounded to media/reaction endpoints | Router delegates to service for reactions, available users, voice upload/stream, file upload | `cd backend && pytest -q` | `docs/status/wave2a/W2A-SR-002_STATUS.md` | No | `done` |
| `W2A-SR-003` | `backend/tests/architecture/**` or `backend/tests/unit/**` | Lightweight guard only for completed module boundaries | Add robust check: router layer should not own direct ORM calls for finished module(s) | `cd backend && pytest -q` | `docs/architecture/W2A_ARCHITECTURE_GUARDS.md`, `docs/status/wave2a/W2A-SR-003_STATUS.md` | No | `done` |
| `W2A-SR-010` | `backend/app/api/v1/endpoints/services.py` | Mixed-risk file (catalog + queue-adjacent routes) | Isolate safe catalog endpoints first; defer queue-adjacent handlers | `cd backend && pytest -q` + `pytest tests/test_openapi_contract.py -q` | `docs/status/wave2a/W2A-SR-010_STATUS.md` | Yes (queue-adjacent) | `pending human review` |
| `W2A-SR-020` | `backend/app/api/v1/endpoints/admin_departments.py` | Contains queue settings endpoints | Router -> service -> repository with queue settings isolation | `cd backend && pytest -q` | `docs/status/wave2a/W2A-SR-020_STATUS.md` | Yes (queue) | `pending human review` |
| `W2A-SR-030` | `backend/app/api/v1/endpoints/doctor_integration.py` | Queue-coupled workflow | Move orchestration out of router | `cd backend && pytest -q` | `docs/status/wave2a/W2A-SR-030_STATUS.md` | Yes (queue) | `pending human review` |
| `W2A-SR-040` | `backend/app/api/v1/endpoints/visits.py` | Updates queue state alongside visit state | Extract transaction flow into service/repository | `cd backend && pytest -q` + targeted integration | `docs/status/wave2a/W2A-SR-040_STATUS.md` | Yes (queue) | `pending human review` |
| `W2A-SR-050` | `backend/app/api/v1/endpoints/registrar_integration.py` | Queue-heavy orchestration | Service use-case orchestration + repository query isolation | `cd backend && pytest -q` | `docs/status/wave2a/W2A-SR-050_STATUS.md` | Yes (queue) | `pending human review` |
| `W2A-SR-060` | `backend/app/api/v1/endpoints/registrar_wizard.py` | Queue + payment crossover | Decompose router transactions into service/repository | `cd backend && pytest -q` | `docs/status/wave2a/W2A-SR-060_STATUS.md` | Yes (queue + payments) | `pending human review` |
| `W2A-SR-070` | `backend/app/api/v1/endpoints/qr_queue.py` | High-density queue mutation logic | Service transaction orchestration, repository DB operations | `cd backend && pytest -q` | `docs/status/wave2a/W2A-SR-070_STATUS.md` | Yes (queue) | `pending human review` |
| `W2A-SR-080` | `backend/app/api/v1/endpoints/cashier.py` | Payment-critical flows | Router thin, service flow rules, repository writes | `cd backend && pytest -q` | `docs/status/wave2a/W2A-SR-080_STATUS.md` | Yes (payments) | `pending human review` |
| `W2A-SR-090` | `backend/app/api/v1/endpoints/appointments.py` | Includes pending payment logic | Extract payment-centric queries from router | `cd backend && pytest -q` | `docs/status/wave2a/W2A-SR-090_STATUS.md` | Yes (payments) | `pending human review` |
| `W2A-SR-100` | `backend/app/api/v1/endpoints/admin_stats.py` | Aggregates payment data in router | Service/reporting orchestration + repository querying | `cd backend && pytest -q` | `docs/status/wave2a/W2A-SR-100_STATUS.md` | Yes (payments) | `pending human review` |

## Initial Execution Selection

- Execute now: `W2A-SR-001`, `W2A-SR-002`, `W2A-SR-003`
- Defer: `W2A-SR-010+` (protected or mixed-protected modules)
