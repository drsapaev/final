# Wave 2C Confirmation Runtime Behavior

Date: 2026-03-07
Mode: analysis-first, docs-only

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
7. `queue_service.get_next_queue_number(...)`
8. `queue_service.create_queue_entry(..., source="confirmation", visit_id=...)`
9. visit status becomes `open`

Registrar bridge path:

- `backend/app/api/v1/endpoints/registrar_wizard.py`
- separate `confirm_visit_by_registrar(...)`
- separate `_assign_queue_numbers_on_confirmation(...)`
- creates `OnlineQueueEntry(source="confirmation")` directly in that family

## Duplicate Check Before `create_queue_entry()`

No canonical duplicate check was found in the public confirmation service before
calling `queue_service.create_queue_entry(...)`.

Observed behavior:

- repository lookup checks only whether the visit is still
  `pending_confirmation`
- security checks validate token and replay/rate conditions
- no lookup blocks allocation because the patient already has an active row in
  the same queue/day

## Does Confirmation Create A New Queue Entry Even If An Active Entry Exists?

Yes.

Characterization evidence:

- `test_confirmation_split_flow_with_existing_active_entry_creates_second_active_row`
  proves that a pre-existing `waiting` row for the same patient and queue does
  not block confirmation allocation
- after confirmation, two active `waiting` rows remain in the same queue:
  one `source="online"` row and one `source="confirmation"` row

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
but it does prove a read-before-write race window exists.

## Runtime Verdict

The current confirmation family behaves as follows:

- creates queue entries for same-day confirmation
- uses fresh ticket allocation through legacy queue helpers
- does not run a canonical duplicate-policy gate before allocation
- can create a second active row in the same queue/day for the same patient

That runtime behavior is real and already characterized. It is not a hypothesis.
