# Wave 2C QR Boundary Migration Status

Date: 2026-03-09
Mode: behavior-preserving migration
Status: `completed`

## Files Changed

- `backend/app/services/qr_full_update_queue_assignment_service.py`
- `backend/app/services/queue_service.py`
- `backend/tests/unit/test_qr_create_branch_extraction.py`
- `backend/tests/unit/test_qr_payload_compatibility.py`
- `docs/status/W2C_QR_BOUNDARY_MIGRATION_PLAN.md`
- `docs/architecture/W2C_QR_BOUNDARY_MIGRATION.md`
- `docs/status/W2C_QR_BOUNDARY_MIGRATION_STATUS.md`

## Old Behavior

Mounted QR full-update additional-service rows were created directly inside the
QR-local seam after QR-local raw SQL numbering.

## New Behavior

Mounted QR full-update additional-service rows still use the same QR-local raw
SQL numbering, but row creation now goes through:

- `QueueDomainService.allocate_ticket(allocation_mode="create_entry", ...)`

The compatibility boundary then delegates to legacy
`queue_service.create_queue_entry(...)`.

## Behavior Verification

Verified unchanged:

- consultation keeps original `queue_time`
- additional services create independent entries
- numbering remains unchanged
- `queue_time` remains unchanged
- `source` inheritance remains unchanged
- QR payload fields `birth_year` and `address` remain persisted
- response shape remains unchanged

## Tests Run

- `cd backend && pytest tests/characterization/test_qr_queue_direct_sql_characterization.py -q -c pytest.ini`
- `cd backend && pytest tests/characterization/test_qr_queue_direct_sql_concurrency.py -q -c pytest.ini`
- `cd backend && pytest tests/unit/test_qr_create_branch_extraction.py tests/unit/test_qr_payload_compatibility.py tests/unit/test_queue_allocator_boundary.py -q`
- `cd backend && pytest tests/characterization -q -c pytest.ini`
- `cd backend && pytest tests/test_openapi_contract.py -q`
- `cd backend && pytest -q`

## Results

- QR characterization: `4 passed`
- QR concurrency characterization: `2 passed`
- QR/unit/boundary tests: `8 passed`
- full characterization suite: `41 passed`
- OpenAPI contract: `10 passed`
- full backend suite: `753 passed, 3 skipped`

## Remaining Deferred Families

- force-majeure allocator family
- `OnlineDay` legacy family
- broader QR cleanup outside the mounted full-update create branch
