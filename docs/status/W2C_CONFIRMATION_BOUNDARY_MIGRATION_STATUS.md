# Wave 2C Confirmation Boundary Migration Status

Date: 2026-03-07
Mode: behaviour-preserving migration
Status: `done`

## Scope

Migrated only the mounted confirmation family:

- `backend/app/services/visit_confirmation_service.py`
- mounted registrar confirmation bridge via
  `backend/app/api/v1/endpoints/registrar_wizard.py` because it already
  delegates to `VisitConfirmationService.assign_queue_numbers_on_confirmation()`

Not migrated:

- `qr_queue.py` direct SQL branches
- `OnlineDay` legacy allocators
- `force_majeure` allocator paths
- broader registrar batch/wizard allocator families
- unmounted duplicate confirmation modules

## Old Path

When confirmation needed a new queue row:

1. `queue_service.get_next_queue_number(...)`
2. direct `queue_service.create_queue_entry(...)`

## New Path

When confirmation needs a new queue row:

1. `queue_service.get_next_queue_number(...)` remains unchanged
2. `VisitConfirmationService` calls
   `QueueContextFacade(QueueDomainServiceContractAdapter).allocate_ticket(...)`
3. the facade delegates to `QueueDomainService.allocate_ticket(...)`
4. `QueueDomainService.allocate_ticket(...)` still delegates to the legacy
   allocator internally

## Preserved Behavior

- reuse-existing-entry branch is unchanged
- ambiguous ownership still returns explicit `409`
- no new ticket is allocated when an existing active entry is reused
- ticket numbering algorithm is unchanged
- `queue_time` and fairness ordering are unchanged
- mounted registrar confirmation bridge still returns the same response shape

## Legacy Helper Still Kept

`queue_service.get_next_queue_number(...)` remains a direct helper call in the
confirmation family because the current compatibility boundary owns queue-row
creation, not standalone number reservation. Removing that helper would expand
this slice into allocator redesign.

## Tests Run

- `cd backend && pytest tests/unit/test_confirmation_reuse_existing_entry.py tests/unit/test_visit_confirmation_service.py tests/unit/test_queue_allocator_boundary.py -q`
- `cd backend && pytest tests/characterization/test_confirmation_split_flow_characterization.py -q -c pytest.ini`
- `cd backend && pytest tests/characterization/test_confirmation_split_flow_concurrency.py -q -c pytest.ini`
- `cd backend && pytest tests/characterization -q -c pytest.ini`
- `cd backend && pytest tests/test_openapi_contract.py -q`
- `cd backend && pytest -q`

## Results

- targeted unit tests: `10 passed`
- confirmation characterization: `6 passed`
- confirmation concurrency characterization: `2 passed`
- full characterization suite: `15 passed`
- OpenAPI contract: `10 passed`
- full backend suite: `705 passed, 3 skipped`

## Deferred After This Slice

- registrar batch-only allocator family
- `qr_queue.py` direct SQL allocator family
- `force_majeure` allocator family
- `OnlineDay` legacy allocator family
- unmounted confirmation duplicate module cleanup
