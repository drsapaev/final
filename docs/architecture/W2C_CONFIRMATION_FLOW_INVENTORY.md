# Wave 2C Confirmation Flow Inventory

Date: 2026-03-07
Mode: analysis-first, characterization-first

## Scope

This document inventories the runtime modules and duplicate code paths that take
part in confirmation-based queue joins.

## Entry Points and Internal Steps

| File | Function | Role in flow | Inputs | Outputs | Numbering occurs | Duplicate checks occur | Queue entry created | Visit link created or updated |
|---|---|---|---|---|---|---|---|---|
| `backend/app/services/doctor_integration_api_service.py` | visit scheduling flow that creates `pending_confirmation` visits | Pre-confirmation producer | patient, doctor, services, `confirmation_channel`, visit date/time | `Visit(status="pending_confirmation")` plus `confirmation_token` | No | No | No | Creates the initial `Visit` and `VisitService` rows |
| `backend/app/api/v1/endpoints/visit_confirmation.py` | `confirm_visit_by_telegram()` | Mounted public token-based confirmation endpoint | token, Telegram user metadata, request IP and UA | `ConfirmationResponse` | Indirect only, through service | Indirect only, through service and security validation | Indirect only | Updates `Visit` through service |
| `backend/app/api/v1/endpoints/visit_confirmation.py` | `confirm_visit_by_pwa()` | Mounted public PWA confirmation endpoint | token, patient phone, request IP and UA | `ConfirmationResponse` | Indirect only | Indirect only | Indirect only | Updates `Visit` through service |
| `backend/app/api/v1/endpoints/visit_confirmation.py` | `get_visit_info_by_token()` | Read-only preview before confirmation | token | visit preview payload | No | Status and expiry validation only | No | No |
| `backend/app/services/visit_confirmation_api_service.py` | `confirm_visit_by_telegram()`, `confirm_visit_by_pwa()` | Duplicate router-style module; not mounted in `api.py` | same as mounted public endpoints | same response model | Indirect only | Indirect only | Indirect only | Same downstream service behavior if called directly |
| `backend/app/services/visit_confirmation_service.py` | `confirm_by_telegram()` | Public Telegram application service | token, Telegram user id, IP, UA | confirmation payload or domain error | No direct numbering; delegates later | Yes, via `ConfirmationSecurityService.validate_confirmation_request()` and `get_pending_visit_by_token()` | Indirect only | Stamps `confirmed_at`, `confirmed_by`, and status |
| `backend/app/services/visit_confirmation_service.py` | `confirm_by_pwa()` | Public PWA application service | token, patient phone, IP, UA | confirmation payload or domain error | No direct numbering; delegates later | Yes, via security validation, token expiry checks, and optional phone match | Indirect only | Same as Telegram path |
| `backend/app/services/visit_confirmation_service.py` | `_confirm_visit()` | Shared confirmation orchestrator | loaded `Visit`, actor metadata | final confirmation payload | Indirect when `visit_date == today` | No queue duplicate check here | Indirect only | Sets `Visit.status` to `confirmed`, then to `open` for same-day confirmations |
| `backend/app/services/visit_confirmation_service.py` | `_assign_queue_numbers_on_confirmation()` | Main public split-flow allocator | same-day `Visit` | `queue_numbers`, `print_tickets` | Yes, via `queue_service.get_next_queue_number()` | No | Yes, via `queue_service.create_queue_entry()` | Yes, created queue row stores `visit_id=visit.id` |
| `backend/app/repositories/visit_confirmation_repository.py` | `get_pending_visit_by_token()` | Pending-visit lookup gate | token | pending `Visit` or `None` | No | Yes, indirectly, because replayed confirmations stop here once status is no longer `pending_confirmation` | No | No |
| `backend/app/repositories/visit_confirmation_repository.py` | `get_or_create_daily_queue()` | Queue ownership resolution | day, specialist, queue tag | `DailyQueue` | No | No | No | No |
| `backend/app/services/confirmation_security.py` | `validate_confirmation_request()` | Security and replay gate | token, IP, UA, channel | `SecurityCheckResult` | No | Yes: token existence, status, expiry, IP and patient rate limits, suspicious activity | No | No |
| `backend/app/services/queue_service.py` | `get_next_queue_number()` | Number allocator used by confirmation flow | `DailyQueue`, `queue_tag` | next queue number | Yes | No | No | No |
| `backend/app/services/queue_service.py` | `create_queue_entry()` | Queue row persistence helper used by confirmation flow | `DailyQueue`, `visit_id`, `patient_id`, number, source | persisted `OnlineQueueEntry` | Uses explicit `number` passed by caller in confirmation flow | No | Yes | Yes, because `visit_id` is passed in |
| `backend/app/api/v1/endpoints/registrar_wizard.py` | `confirm_visit_by_registrar()` | Mounted registrar confirmation bridge | `visit_id`, manual confirmation payload, registrar auth | `ConfirmVisitResponse` | Indirect only | Status and expiry checks only | Indirect only | Updates `Visit` directly in router flow |
| `backend/app/api/v1/endpoints/registrar_wizard.py` | `_assign_queue_numbers_on_confirmation()` | Mounted registrar split-flow helper | same-day `Visit` | `queue_numbers`, `print_tickets` | Yes, via `queue_service.get_next_queue_number()` | No | Yes, but with manual `OnlineQueueEntry(...)` construction | Yes, `visit_id` and explicit `session_id` are set directly |
| `backend/app/services/registrar_wizard_api_service.py` | `confirm_visit_by_registrar()`, `_assign_queue_numbers_on_confirmation()` | Duplicate API-service mirror of mounted registrar flow | same as mounted registrar flow | same | Yes in helper | No | Yes | Yes |

## Inventory Notes

- Public token confirmation is mounted through
  `app.api.v1.endpoints.visit_confirmation`.
- Registrar confirmation is a separate mounted bridge through
  `app.api.v1.endpoints.registrar_wizard`.
- Both mounted confirmation families use split allocation:
  - number lookup happens before row persistence
  - there is no queue duplicate pre-check in the confirmation-specific path
- The queue row source is `confirmation` in both mounted families.
