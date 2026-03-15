# Two Factor SMS Email API Service Cleanup Plan

Scope:
- review detached `backend/app/services/two_factor_sms_email_api_service.py`
- review detached `backend/app/repositories/two_factor_sms_email_api_repository.py`
- prove the mounted `/api/v1/2fa` SMS/email contract before any deletion
- repair only the narrow live frontend/backend parity gap if evidence confirms
  that the UI is sending the wrong request shape

Evidence:
- the live routes are mounted from
  `backend/app/api/v1/endpoints/two_factor_sms_email.py`
- `backend/openapi.json` contains the published SMS/email 2FA routes
- live frontend usage remains in
  `frontend/src/components/security/SMSEmail2FA.jsx` and
  `frontend/src/components/security/TwoFactorManager.jsx`
- no confirmed backend, test, docs, or frontend imports of the detached pair
  remain
- diff vs the mounted owner is non-behavioral typing/import drift only
- frontend audit confirms that `SMSEmail2FA.jsx` still sends JSON bodies to
  send/verify routes that are implemented as query-param endpoints

Why this is safe:
- dedicated endpoint proof lands before deleting the detached pair
- the only live mutation allowed here is the narrow frontend parity repair
  needed to match the already-published backend contract
- verification covers backend OpenAPI/boundary/RBAC checks and a targeted
  frontend component test

Out of scope:
- rewriting the broader 2FA login flow
- changing TOTP setup/verification behavior
- touching websocket-auth runtime
