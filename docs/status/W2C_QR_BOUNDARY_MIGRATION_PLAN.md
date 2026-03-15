# Wave 2C QR Boundary Migration Plan

Date: 2026-03-09
Mode: narrow caller migration

## Files In Scope

- `backend/app/api/v1/endpoints/qr_queue.py`
- `backend/app/services/qr_full_update_queue_assignment_service.py`
- `backend/app/services/queue_domain_service.py` only if the QR caller needs
  a strictly minimal compatibility touch
- `backend/app/services/queue_service.py` only if the compatibility boundary
  needs a narrow create-entry passthrough to preserve current QR behavior
- QR-only tests and Wave 2C migration docs

## Exact Migration Point

The migration point is the QR-local create-branch materialization inside
`QRFullUpdateQueueAssignmentService._materialize_create_branch_handoff(...)`.

Current path:

- QR seam computes raw SQL `MAX(number)+1`
- QR seam computes QR-local `session_id`
- QR seam creates `OnlineQueueEntry` directly

Target path:

- QR seam still computes raw SQL `MAX(number)+1`
- QR seam still computes QR-local `session_id`
- QR seam calls
  `QueueDomainService.allocate_ticket(allocation_mode="create_entry", ...)`
  with explicit `number`, `queue_time`, `session_id`, `birth_year`,
  `address`, `services`, and `service_codes`

## Why This Is Safe

- Numbering remains QR-local and raw-SQL based for this slice.
- `queue_time` remains QR-local and is still passed explicitly.
- `source` inheritance remains QR-local and is still passed explicitly.
- Additional services still create independent rows.
- Consultation behavior stays outside this create branch.
- Public `/queue/join/start` and `/queue/join/complete` are untouched.

## What Remains Out Of Scope

- Replacing raw SQL numbering
- Redesigning duplicate policy or canonical duplicate gate
- Changing `queue_session` semantics
- Refactoring broader QR orchestration
- Any OnlineDay, force-majeure, registrar, or confirmation work
