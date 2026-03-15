# Two Factor SMS Email API Service Cleanup

`backend/app/services/two_factor_sms_email_api_service.py` and
`backend/app/repositories/two_factor_sms_email_api_repository.py` were handled
as a protected auth-adjacent duplicate pair, not as a blind-delete candidate.

Verified facts:
- `backend/app/api/v1/api.py` mounts
  `backend/app/api/v1/endpoints/two_factor_sms_email.py` under `/api/v1/2fa`
- `backend/openapi.json` publishes the live SMS/email 2FA surface:
  - `/api/v1/2fa/send-code`
  - `/api/v1/2fa/verify-code`
  - `/api/v1/2fa/verification-status`
  - `/api/v1/2fa/resend-code`
  - `/api/v1/2fa/supported-methods`
  - `/api/v1/2fa/security-logs`
  - `/api/v1/2fa/recovery-methods`
- live frontend usage remains in:
  - `frontend/src/components/security/SMSEmail2FA.jsx`
  - `frontend/src/components/security/TwoFactorManager.jsx`
  - `frontend/src/pages/Login.jsx`
  - `frontend/src/pages/SecurityPage.jsx`
- no live imports of the detached service or repository remained in
  `backend/app`, `backend/tests`, `docs`, or `frontend`
- diff vs the mounted owner was limited to typing/import drift
- frontend audit exposed a live parity gap: `SMSEmail2FA.jsx` was still sending
  JSON bodies to `/api/v1/2fa/send-code` and `/api/v1/2fa/verify-code` while
  the mounted backend owner expects query-string parameters

Cleanup performed:
- added `backend/tests/integration/test_two_factor_sms_email_endpoint_contract.py`
  to protect the mounted SMS/email 2FA contract
- updated `frontend/src/components/security/SMSEmail2FA.jsx` to follow the
  backend query-string contract for send/verify flows
- added `frontend/src/components/security/__tests__/SMSEmail2FA.test.jsx`
  to protect the frontend request format
- deleted detached `backend/app/services/two_factor_sms_email_api_service.py`
- deleted detached `backend/app/repositories/two_factor_sms_email_api_repository.py`

Effect:
- no mounted `/api/v1/2fa/*` route was removed
- the detached duplicate pair is gone
- the live SMS/email 2FA UI now matches the mounted backend contract instead
  of sending unsupported JSON payloads
- protected auth cleanup moved forward without rewriting TOTP, pending-token,
  or websocket-auth runtime
