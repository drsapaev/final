# W2D Remaining Residue Strategic Audit

## Summary

The bounded W2D duplicate-cleanup lane has been pushed to the point where the
remaining candidate pool is no longer a blind-delete queue.

Current verdict:

- clean low-risk duplicate cleanup is effectively exhausted
- the remaining files split into three different buckets
- further autonomous work should switch from silent deletion to explicit
  planning gates

## Bucket 1: Mixed-risk but non-protected

These files are outside the protected domains, but they no longer pass the
behavior-preserving cleanup gate.

Resolved since this audit:

- `activation` moved out of this bucket after a dedicated equivalence check
  confirmed that the mounted owner and `ActivationAdminService` stack preserve
  the live admin contract while the detached `activation_api_service.py` pair
  had no live imports
- `settings` moved out of this bucket via a dedicated contract-restoration
  slice that mounted the live backend owner and removed only proven orphan
  residue around that surface
- `clinic_management` moved out of this bucket after a dedicated router parity
  slice ported equipment branch-scope wiring into the mounted owner and removed
  the detached duplicate
- `admin_providers` moved out of the protected residue pool after a dedicated
  endpoint-contract slice proved the live `/api/v1/admin/providers*` surface,
  repaired a narrow update-schema gap, and removed the detached duplicate
- `payment_settings` moved out of the protected residue pool after dedicated
  endpoint proof confirmed that the mounted owner already preserved the live
  contract and the detached service/repository pair had no live imports
- `admin_users` moved out of the protected residue pool after dedicated
  endpoint/RBAC proof confirmed the mounted `/api/v1/admin/users` contract and
  allowed the detached service/repository pair to be removed
- `minimal_auth` moved out of the protected residue pool after dedicated
  endpoint proof confirmed that the mounted `/api/v1/auth/minimal-login`
  contract already ran through the live `AuthFallbackService` stack and the
  detached service/repository pair had no live imports
- `simple_auth` moved out of the protected residue pool after dedicated
  endpoint proof confirmed that the mounted `/api/v1/auth/simple-login`
  contract already ran through the live `AuthFallbackService` stack while the
  live `/api/v1/auth/me` authenticated profile contract remained intact
- `password_reset` moved out of the protected residue pool after dedicated
  endpoint proof confirmed the mounted `/api/v1/password-reset/*` recovery
  contract, the detached service/repository pair had no live imports, and a
  narrow `require_roles(...)` fix restored the intended admin-only statistics
  RBAC path in the mounted owner
- `phone_verification` moved out of the protected residue pool after dedicated
  endpoint proof confirmed both the mounted user-facing and admin-facing
  `/api/v1/phone-verification/*` contracts, the detached service/repository
  pair had no live imports, and narrow `require_roles(...)` fixes restored the
  intended RBAC path for statistics and admin send-code in the mounted owner
- `two_factor_devices` moved out of the protected residue pool after dedicated
  runtime-contract proof confirmed that the detached service/repository pair
  had no live imports, the unique `two_factor_devices.py` routes preserved
  their contract, and the current shadowed `GET/DELETE /api/v1/2fa/devices*`
  runtime contract was captured explicitly before deletion
- `two_factor_sms_email` moved out of the protected residue pool after
  dedicated endpoint proof confirmed the mounted `/api/v1/2fa` SMS/email
  routes, a narrow frontend parity repair aligned the live `SMSEmail2FA`
  client with the backend query-string contract, and the detached
  service/repository pair had no live imports
- `websocket_auth` moved out of the protected residue pool after dedicated
  websocket runtime-contract proof confirmed that the live `/api/v1/ws-auth/*`
  surface still belonged to the mounted endpoint owner, the detached service
  had no live imports, and two narrow mounted-owner fixes restored parity with
  the live `WSManager` async/sync interface
- `queue_auto_close` and `wait_time_analytics` moved out of the protected
  residue pool after dedicated endpoint-contract proof confirmed that both
  mounted queue-adjacent surfaces still belonged to their live endpoint owners,
  the detached service files had no live imports, and narrow mounted-owner
  RBAC fixes restored the SSOT `require_roles(...)` call shape
- `section_templates` moved out of the protected residue pool after dedicated
  endpoint proof confirmed that the mounted `/api/v1/section-templates/*`
  surface remained the live owner, the detached service/repository pair had no
  live imports, and the only diff vs the mounted owner was typing/import drift
- `emr_export` moved out of the protected residue pool after dedicated
  endpoint proof confirmed that the mounted `/api/v1/emr/export/*` surface
  remained the live owner, the detached service/repository pair had no live
  imports, and the only diff vs the mounted owner was typing/import drift
- `emr_versioning_enhanced` moved out of the protected residue pool after
  dedicated endpoint proof confirmed that the mounted
  `/api/v1/emr/versions/*` surface remained the live owner, the detached
  service/repository pair had no live imports, and the only diff vs the
  mounted owner was typing/import drift
- `emr_lab_integration` moved out of the protected residue pool after
  dedicated endpoint proof confirmed that the mounted `/api/v1/emr/lab/*`
  surface remained the live owner, the detached service/repository pair had no
  live imports, and the only diff vs the mounted owner was typing/import drift
- `emr_ai` moved out of the protected residue pool after dedicated endpoint
  proof confirmed that the mounted `/api/v1/emr/ai/*` surface remained the
  live owner, the detached service/repository pair had no live imports, and
  the only diff vs the mounted owner was typing/import drift
- `emr_ai_enhanced` moved out of the protected residue pool after dedicated
  endpoint proof confirmed that the mounted `/api/v1/emr/ai-enhanced/*`
  surface remained the live owner, the detached service/repository pair had no
  live imports, the only diff vs the mounted owner was typing/import drift,
  and a narrow mounted-owner fix restored the live `emr/{emr_id}/ai-enhance`
  CRUD call path

Current state:

- no remaining mixed-risk non-protected candidates are approved for autonomous
  cleanup at this time

## Bucket 2: Protected audit-only

These candidates must not be mutated without a separate plan-gate because they
sit inside protected domains or directly adjacent contract-sensitive runtime.

### IAM / auth-adjacent

No remaining auth-adjacent cleanup or parity candidates are approved here.

Cluster notes:

- the mixed `/api/v1/2fa/devices*` ownership tail has now been resolved as a
  parity issue without router reordering
- runtime first-match still belongs to
  `backend/app/api/v1/endpoints/two_factor_auth.py` for the shadowed `GET` and
  `DELETE` routes
- published OpenAPI now matches that live auth-owner contract for the shadowed
  routes, while the remaining unique device-management routes stay published
  from `backend/app/api/v1/endpoints/two_factor_devices.py`

Verdict:

- treat the split 2FA device surface as a live documented architecture choice,
  not as remaining residue

### Payment / cashier / provider-adjacent

No remaining payment-adjacent cleanup candidates are approved here.

Cluster notes:

- `cashier_api_service.py` was reclassified out of the cleanup queue: it is a
  payment-critical architecture artifact with live boundary-test dependency,
  not a silent-delete candidate
- `GET /api/v1/2fa/devices` and `DELETE /api/v1/2fa/devices/{device_id}` still
  resolve first to hidden handlers in
  `backend/app/api/v1/endpoints/two_factor_auth.py`, while the remaining
  device-management routes are owned by
  `backend/app/api/v1/endpoints/two_factor_devices.py`; this is a protected
  contract/ownership tail, not a new cleanup candidate

### Queue-adjacent

No remaining queue-adjacent cleanup candidates are approved here.

### EMR / clinical

No remaining EMR / clinical cleanup candidates are approved here.

Verdict:

- protected duplicate/parity cleanup is exhausted
- only non-cleanup architecture review surfaces remain

## Bucket 3: Not cleanup candidates

These files survived screening because they are still live service owners or
explicitly imported runtime modules, not detached residue.

Examples:

- `feature_flags_api_service.py`
- `global_search_api_service.py`
- `messages_api_service.py`
- `services_api_service.py`
- `specialized_panels_api_service.py`
- `cashier_api_service.py`

Verdict:

- do not reopen them as cleanup candidates unless new evidence appears

## Recommended next track

The next honest move is:

- docs/status consolidation after protected residue resolution
- optional separate human-reviewed `cashier_api_service.py` architecture review
  only if that surface becomes a priority
- no further pattern-based duplicate deletion until new evidence appears
