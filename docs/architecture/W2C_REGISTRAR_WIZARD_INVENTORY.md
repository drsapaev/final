# Wave 2C Registrar Wizard Inventory

Date: 2026-03-08
Mode: characterization-only

## In-Scope Runtime Family

### Flow RW-01

- file: `backend/app/api/v1/endpoints/registrar_wizard.py`
- function: `create_cart_appointments()`
- role in flow: mounted registrar wizard cart flow that creates visits, creates an
  invoice, and assigns same-day queue entries
- numbering occurs: yes, but only for same-day confirmed visits through
  `MorningAssignmentService._assign_queues_for_visit()`
- duplicate checks occur: yes, indirectly inside
  `MorningAssignmentService._assign_single_queue()`
- queue entries are created: yes, for same-day visits when queue assignment
  succeeds
- visit linkage changes: yes, new queue entries receive `visit_id`; reused rows
  are returned as-is
- billing/payment side effects: yes, `PaymentInvoice` and `PaymentInvoiceVisit`
  are created in the same request
- mounted and production-relevant: yes

### Flow RW-02

- file: `backend/app/services/morning_assignment.py`
- function: `_assign_queues_for_visit()`
- role in flow: queue-tag expansion layer used by the mounted wizard cart flow
- numbering occurs: yes, per queue tag through `_assign_single_queue()`
- duplicate checks occur: yes, by looking for an existing row in the resolved
  `DailyQueue`
- queue entries are created: yes, through `queue_service.create_queue_entry()`
- visit linkage changes: yes for new rows; reused rows keep their existing link
- billing/payment side effects: no direct payment logic, but it runs inside the
  cart request transaction
- mounted and production-relevant: yes, through `registrar_wizard.py`

### Flow RW-03

- file: `backend/app/api/v1/endpoints/registrar_wizard.py`
- function: `confirm_visit_by_registrar()`
- role in flow: mounted confirmation bridge inside the registrar wizard file
- numbering occurs: yes, for same-day confirmation
- duplicate checks occur: yes, through `VisitConfirmationService`
- queue entries are created: yes, when confirmation allocates a queue row
- visit linkage changes: yes
- billing/payment side effects: no
- mounted and production-relevant: yes
- current disposition: out of scope for this pass because the confirmation family
  already has its own corrected and migrated track

## Adjacent But Out Of Scope

### Flow RW-04

- file: `backend/app/api/v1/endpoints/registrar_wizard.py`
- function: `_create_queue_entries()`
- role in flow: local legacy-style helper with direct `get_next_queue_number()` +
  `create_queue_entry()` logic
- numbering occurs: yes
- duplicate checks occur: no explicit canonical gate
- queue entries are created: yes
- visit linkage changes: no explicit `visit_id` linkage in the helper itself
- billing/payment side effects: no direct payment logic
- mounted and production-relevant: no confirmed mounted caller found in current
  runtime
- current disposition: dead/legacy candidate, not used for this pass

### Flow RW-05

- file: `backend/app/services/registrar_wizard_api_service.py`
- function: `create_cart_appointments()` and mirrored helpers
- role in flow: duplicate service module that mirrors registrar wizard router logic
- numbering occurs: yes, in the mirrored implementation
- duplicate checks occur: yes, in the mirrored implementation
- queue entries are created: yes, in the mirrored implementation
- visit linkage changes: yes
- billing/payment side effects: yes
- mounted and production-relevant: no mounted inclusion found in
  `backend/app/api/v1/api.py`
- current disposition: duplicate/unmounted reference only

### Flow RW-06

- file: `backend/app/api/v1/endpoints/registrar_integration.py`
- functions: remaining non-batch registrar branches such as
  `create_registrar_appointment()`, `generate_qr_for_registrar()`,
  `start_queue_visit()`
- role in flow: registrar operations adjacent to the wizard domain
- numbering occurs: not as part of the broader registrar wizard cart flow
- duplicate checks occur: not as part of the wizard cart allocator path
- queue entries are created: not in the narrow mounted wizard/cart path analyzed
  here
- visit linkage changes: yes in lifecycle branches, but outside this pass
- billing/payment side effects: possible in lifecycle branches
- mounted and production-relevant: yes
- current disposition: explicitly excluded from this pass

## Inventory Verdict

The only production-relevant allocator subfamily still inside the broader
registrar wizard track is the mounted `/registrar/cart` flow plus the
`MorningAssignmentService` path it invokes for same-day visits.

Everything else in this pass is either:

- already handled in another queue-family track (`confirm_visit_by_registrar`)
- dead or duplicate (`_create_queue_entries`, `registrar_wizard_api_service.py`)
- adjacent but not part of the mounted wizard allocator path
