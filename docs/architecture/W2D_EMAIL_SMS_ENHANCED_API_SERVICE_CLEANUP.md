# Email SMS Enhanced API Service Cleanup

`backend/app/services/email_sms_enhanced_api_service.py` was a detached
router-style residue for the mounted enhanced email/SMS endpoint owner.

Verified facts:
- `backend/app/api/v1/api.py` mounts
  `backend/app/api/v1/endpoints/email_sms_enhanced.py` with
  `prefix="/email-sms"`
- `backend/openapi.json` exposes the live `/api/v1/email-sms/*` routes owned
  by the mounted endpoint file, including enhanced reminder, lab results,
  bulk email, bulk SMS, template, and statistics routes
- no live source imports of
  `backend/app/services/email_sms_enhanced_api_service.py` were found in
  `backend/app`, `backend/tests`, `docs`, or `frontend`
- `backend/app/services/email_sms_enhanced_api_service.py` differed from the
  mounted owner only by stale imports and typing drift and no longer owned
  runtime route behavior

Cleanup performed:
- removed `backend/app/services/email_sms_enhanced_api_service.py`

Effect:
- no mounted runtime route was removed
- live enhanced email/SMS route ownership remains unchanged
- one more dead router-style service residue is gone
