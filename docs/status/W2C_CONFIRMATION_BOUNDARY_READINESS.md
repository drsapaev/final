# Wave 2C Confirmation Boundary Readiness

Date: 2026-03-07
Mode: characterization-first
Decision: `READY_AFTER_CONTRACT_CLARIFICATION`

## Why This Is Not Boundary-Ready Yet

Characterization now proves the public confirmation flow well enough to avoid
guessing, but the family is still not ready for a direct migration to
`QueueDomainService.allocate_ticket()` for three reasons:

1. Confirmation still has two mounted implementations:
   - public token flow in `visit_confirmation.py`
   - registrar bridge in `registrar_wizard.py`
2. Current runtime behavior allows confirmation to create a second active queue
   row when the patient already has a waiting row in the same queue.
3. Parallel validation and pending-visit lookup can both observe the same
   `pending_confirmation` visit before status flips, so any migration that
   reorders validation and persistence could change behavior.

## What Characterization Confirmed

- same-day public confirmation allocates the next number and creates a queue row
  with `source="confirmation"`
- created queue row links back to `visit_id`
- replayed public confirmation returns an error and does not create a second
  confirmation row
- registrar confirmation also creates `source="confirmation"` queue rows
- pre-existing active queue rows do not block confirmation-based queue creation

## What Still Needs Clarification

- Should confirmation preserve the current "create another active row" behavior
  when an active queue entry already exists for that patient?
- Should public confirmation and registrar confirmation be migrated as one
  family or as two separate compatibility slices?
- Is `allocate_ticket(allocation_mode="create_entry")` enough for confirmation,
  or should the boundary own the split allocation preconditions too?

## Current Verdict

`QueueDomainService.allocate_ticket()` can support the persistence side of the
flow, but migrating the confirmation family safely still requires a domain-level
decision on duplicate-preserving behavior and family boundaries.
