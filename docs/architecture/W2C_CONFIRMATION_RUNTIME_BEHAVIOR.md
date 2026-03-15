# Wave 2C Confirmation Runtime Behavior

Date: 2026-03-07
Mode: post-boundary-migration runtime snapshot

## Runtime Sources Reviewed

- `backend/app/api/v1/endpoints/visit_confirmation.py`
- `backend/app/services/visit_confirmation_service.py`
- `backend/app/repositories/visit_confirmation_repository.py`
- `backend/tests/characterization/test_confirmation_split_flow_characterization.py`
- `backend/tests/characterization/test_confirmation_split_flow_concurrency.py`

## Runtime Path

Mounted public confirmation path:

1. `POST /api/v1/telegram/visits/confirm` or
   `POST /api/v1/patient/visits/confirm`
2. `VisitConfirmationService.confirm_by_telegram()` or
   `VisitConfirmationService.confirm_by_pwa()`
3. `ConfirmationSecurityService.validate_confirmation_request(...)`
4. `VisitConfirmationRepository.get_pending_visit_by_token(token)`
5. `_confirm_visit(...)`
6. `_assign_queue_numbers_on_confirmation(...)` for same-day visits
7. canonical active-entry gate checks existing rows in the same queue/day
8. if a reusable active row exists:
   - reuse it
   - keep its `number`
   - keep its `queue_time`
9. if no reusable active row exists:
   - `queue_service.get_next_queue_number(...)`
   - `QueueContextFacade.allocate_ticket(...)`
   - `QueueDomainService.allocate_ticket(...)`
   - legacy `queue_service.create_queue_entry(..., source="confirmation", visit_id=...)`
10. visit status becomes `open`

Registrar bridge path:

- `backend/app/api/v1/endpoints/registrar_wizard.py`
- separate `confirm_visit_by_registrar(...)`
- separate `_assign_queue_numbers_on_confirmation(...)`
- but the helper delegates to `VisitConfirmationService.assign_queue_numbers_on_confirmation()`
- therefore mounted registrar confirmation now follows the same runtime path as
  mounted public confirmation

## Duplicate Check Before `create_queue_entry()`

A narrow canonical active-entry gate now exists before queue-row creation.

Observed behavior:

- repository lookup still verifies that the visit is `pending_confirmation`
- security checks still validate token and replay/rate conditions
- confirmation now checks canonical active rows in the target queue/day before
  allocating a new row
- no new queue row is created if an existing active row is clearly reusable

## Does Confirmation Create A New Queue Entry Even If An Active Entry Exists?

Not in the mounted confirmation family when ownership is clear.

Characterization evidence after correction:

- `test_confirmation_split_flow_with_existing_active_entry_reuses_existing_row`
  proves that a pre-existing active row in the same queue/day is reused
- `test_confirmation_split_flow_returns_explicit_error_on_ambiguous_existing_entries`
  proves that ambiguous ownership returns explicit `409`
- no same-queue duplicate active row is created by the mounted confirmation
  flows in the clear-ownership case

## Replay And Concurrency Reality

### Replay after a successful confirmation

Observed and tested:

- replayed confirmation returns an error
- no second confirmation-based row is created in that replay case

### Parallel validation / lookup

Observed and tested:

- two parallel validations can both see the same pending token as currently
  allowed
- two parallel pending-visit lookups can both observe the same pending visit
  before the status flips

This does not prove duplicate rows are committed in practice for the same token,
but it still proves a read-before-write race window exists around validation and
pending-visit lookup.

## Runtime Verdict

The current mounted confirmation family behaves as follows:

- same-day confirmation reuses an existing active row when ownership is clear
- ambiguous ownership returns explicit `409`
- otherwise new queue-row creation still uses the legacy numbering helper and
  legacy allocator implementation behind the compatibility boundary
- canonical duplicate behavior for this mounted family now matches the approved
  confirmation intent

Remaining legacy behavior is limited to allocator internals, not same-queue
duplicate creation in the mounted confirmation path.
