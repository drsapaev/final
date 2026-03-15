# Phone Verification API Service Cleanup

`backend/app/services/phone_verification_api_service.py` and
`backend/app/repositories/phone_verification_api_repository.py` were handled
as a protected auth-adjacent duplicate pair, not as a blind-delete candidate.

Verified facts:
- `backend/app/api/v1/api.py` mounts
  `backend/app/api/v1/endpoints/phone_verification.py` under
  `/api/v1/phone-verification`
- `backend/openapi.json` publishes the live phone-verification surface:
  - `/api/v1/phone-verification/send-code`
  - `/api/v1/phone-verification/verify-code`
  - `/api/v1/phone-verification/status`
  - `/api/v1/phone-verification/cancel`
  - `/api/v1/phone-verification/update-phone`
  - `/api/v1/phone-verification/statistics`
  - `/api/v1/phone-verification/admin/send-code`
- live frontend usage remains in:
  - `frontend/src/components/auth/PhoneVerification.jsx`
  - `frontend/src/components/admin/PhoneVerificationManager.jsx`
- no live imports of the detached service or repository remained in
  `backend/app`, `backend/tests`, `docs`, or `frontend`
- diff vs the mounted owner was limited to typing drift
- the detached repository file was only a thin `Session` adapter with no live
  runtime role

Cleanup performed:
- added `backend/tests/integration/test_phone_verification_endpoint_contract.py`
  to protect both user-facing and admin-facing contracts
- fixed two narrow live auth drifts in
  `backend/app/api/v1/endpoints/phone_verification.py` by changing:
  - `require_roles(["Admin", "SuperAdmin"])` on `/statistics`
  - `require_roles(["Admin", "SuperAdmin"])` on `/admin/send-code`
  into positional-role calls accepted by the dependency factory
- deleted detached `backend/app/services/phone_verification_api_service.py`
- deleted detached `backend/app/repositories/phone_verification_api_repository.py`

Effect:
- no mounted `/api/v1/phone-verification/*` route was removed
- the live phone-verification UI surface now has dedicated endpoint proof
- admin statistics and admin send-code now follow the intended RBAC path
  instead of failing inside the dependency factory
- protected auth cleanup moved forward without touching password-reset, login,
  refresh, websocket-auth, or 2FA runtime
