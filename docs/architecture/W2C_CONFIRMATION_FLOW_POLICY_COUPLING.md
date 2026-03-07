# Wave 2C Confirmation Flow Policy Coupling

Date: 2026-03-07
Mode: analysis-first, characterization-first

| Policy area | Coupling level | Current runtime behavior | Evidence |
|---|---|---|---|
| Numbering | High | Confirmation flow performs split allocation: `get_next_queue_number()` first, then row persistence separately | `VisitConfirmationService._assign_queue_numbers_on_confirmation()` and characterization numbering test |
| Duplicate policy | High | Confirmation flow does not run a queue duplicate pre-check; an existing active row for the same patient does not block creation of a new confirmation row | `test_confirmation_split_flow_with_existing_active_entry_creates_second_active_row` |
| Active entry semantics | Medium | Newly created confirmation rows enter with `status="waiting"`; replay is blocked by visit status, not by queue row state | public flow code and replay characterization |
| QR window rules | None | Confirmation flow does not call `check_queue_time_window()` or QR token validation | no QR-token calls in `VisitConfirmationService` |
| Visit lifecycle | High | Same-day confirmation transitions visit `pending_confirmation -> confirmed -> open`; future-day confirmation remains without queue allocation | `_confirm_visit()` plus existing integration tests |
| Token or session identity | Medium | Public flow is keyed by `confirmation_token`; queue row `session_id` is created indirectly by `queue_service.create_queue_entry()` when `patient_id` exists | `VisitConfirmationRepository.get_pending_visit_by_token()` and `queue_service.create_queue_entry()` |
| Registrar workflow | High | Registrar bridge duplicates confirmation logic in a separate mounted router instead of reusing `VisitConfirmationService` | `registrar_wizard.py::confirm_visit_by_registrar()` |
| Security and replay gate | High | Replay protection lives in `ConfirmationSecurityService.validate_confirmation_request()` and repository lookup of `pending_confirmation` visits | security validation code and replay characterization |

## Coupling Takeaways

- Confirmation flow is not just "create a queue row".
- It is coupled to:
  - visit status transitions
  - token-based replay protection
  - split number allocation
  - specialist identity fallback
- The duplicate-policy gap is explicit:
  - replayed confirmations are blocked
  - pre-existing active queue rows are not considered duplicates

This means a boundary migration that preserves behavior must keep those two
facts separate.
