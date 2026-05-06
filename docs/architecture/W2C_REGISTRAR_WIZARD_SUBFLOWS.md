# Wave 2C Registrar Wizard Runtime Subflows

Date: 2026-03-08
Mode: characterization-only

## RW-SF-01: Same-Day Cart Create With Immediate Queue Assignment

- entry point: `POST /api/v1/registrar/cart`
- numbering step: `MorningAssignmentService._assign_single_queue()` ->
  `queue_service.create_queue_entry(auto_number=True)`
- duplicate step: lookup of an existing `OnlineQueueEntry` for the resolved
  `DailyQueue` and patient
- queue entry creation step: new row only when no existing row is found
- service/visit linkage: creates a new `Visit`, then links new queue rows with
  `visit_id`
- source semantics: new rows are created with `source="desk"`
- side effects: creates visits, invoice, invoice-visit links, then queue rows in
  the same request

## RW-SF-02: Same-Day Cart Create With Existing Queue Claim

- entry point: `POST /api/v1/registrar/cart`
- numbering step: skipped when an existing row is found
- duplicate step: same queue-local lookup inside `_assign_single_queue()`
- queue entry creation step: no new row when a compatible row already exists
- service/visit linkage: new visit is still created; reused queue row keeps its
  existing row data
- source semantics: reused row keeps its original `source`
- side effects: invoice and visit creation still happen even when the queue row is
  reused
- characterization evidence: covered by
  `backend/tests/characterization/test_registrar_wizard_queue_characterization.py`

## RW-SF-03: Same Specialist, Different Queue Tags

- entry point: `POST /api/v1/registrar/cart`
- numbering step: one allocation attempt per unique `queue_tag`
- duplicate step: queue-local per resolved `DailyQueue`, not per specialist-day
- queue entry creation step: multiple rows can be created for one visit when its
  services expand to multiple `queue_tag` values
- service/visit linkage: each created row links to the same visit
- source semantics: new rows are created with `source="desk"`
- side effects: same cart request, same invoice, multiple queue claims

## RW-SF-04: Multi-Visit Cart For Different Specialists

- entry point: `POST /api/v1/registrar/cart`
- numbering step: each created visit is evaluated independently for same-day queue
  assignment
- duplicate step: per resolved queue, not across the full cart
- queue entry creation step: one or more rows per visit depending on queue-tag
  expansion
- service/visit linkage: separate visits get separate queue rows
- source semantics: new rows are created with `source="desk"`
- side effects: one shared invoice for multiple visits, queue assignment done
  after visit creation

## RW-SF-05: Future-Day Cart Create

- entry point: `POST /api/v1/registrar/cart`
- numbering step: none during the request
- duplicate step: none during the request
- queue entry creation step: deferred
- service/visit linkage: visit is created and stays `confirmed`
- source semantics: no queue row yet
- side effects: visit and invoice are created without immediate queue allocation

## RW-SF-06: Confirmation Bridge In The Wizard File

- entry point: `POST /registrar/visits/{visit_id}/confirm`
- numbering step: delegated to `VisitConfirmationService`
- duplicate step: delegated to the confirmation family
- queue entry creation step: handled by the already-separated confirmation track
- service/visit linkage: handled in the confirmation flow
- source semantics: confirmation-specific
- side effects: no invoice creation here
- current disposition: explicitly out of scope for this pass

## Runtime Split

The production-relevant registrar wizard allocator family is not “edit existing
visit” in-place. The mounted runtime behaves as:

1. create visits and invoice through `/registrar/cart`
2. immediately assign same-day queue claims via `MorningAssignmentService`
3. defer future-day queue assignment

No separate mounted “edit existing visit and mutate queue claims” endpoint was
confirmed in this pass.
